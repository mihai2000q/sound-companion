import json
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import CostChatOpenAI, build_agent
from app.api import chat
from app.db.usage import Budget, Ledger, Totals, Usage, record_usage
from tests.test_chat_api import StreamingToolModel, events
from tests.test_search_tool import FakeRetriever, chunk


class FakeStore:
    """In-memory `usage_log`."""

    def __init__(self, rows=None, fail_writes=False):
        self.rows: list[tuple[str, uuid.UUID, Usage]] = rows or []
        self.fail_writes = fail_writes

    def add(self, thread_id, request_id, usage):
        if self.fail_writes:
            raise RuntimeError("database down")
        self.rows.append((thread_id, request_id, usage))

    def request_totals(self, request_id):
        mine = [u for _, r, u in self.rows if r == request_id]
        return Totals(len(mine), sum(u.prompt_tokens for u in mine), sum(u.completion_tokens for u in mine), sum(u.cost for u in mine))

    def total_spend(self):
        return sum(u.cost for _, _, u in self.rows)


def priced(text="", tool_calls=(), prompt=10, completion=5, cost=0.001):
    return AIMessage(
        text, tool_calls=list(tool_calls), usage_metadata={"input_tokens": prompt, "output_tokens": completion, "total_tokens": prompt + completion},
        response_metadata={"model_name": "fake/model", "token_usage": {"cost": cost}},
    )


class PricedModel(StreamingToolModel):
    """Streams like the base fake, then a last chunk with the reply's usage, as OpenRouter does."""

    def _stream(self, messages, *args, **kwargs):
        replies, reply = self.messages, next(self.messages)
        self.messages = iter([reply])  # the base class reads the same reply
        try:
            yield from super()._stream(messages, *args, **kwargs)
        finally:
            self.messages = replies
        yield ChatGenerationChunk(
            message=AIMessageChunk(content="", usage_metadata=reply.usage_metadata, response_metadata=reply.response_metadata)
        )


SEARCH = {"name": "search_knowledge_base", "args": {"query": "clarinet"}, "id": "1"}


class Boom:
    """A model or retriever that must not be reached."""

    def __getattr__(self, name):
        raise AssertionError(f"{name} was called")


def client(replies, ledger, retriever=None, model_class=PricedModel, rewriter_model=None):
    app = FastAPI()
    app.include_router(chat.router)
    model = model_class(messages=iter(replies), seen=[], bound=[])
    app.state.agent = build_agent(model, retriever or FakeRetriever([chunk()]), InMemorySaver(), rewriter_model)
    app.state.ledger = ledger
    return TestClient(app)


def ask(test_client, text="hi"):
    return events(test_client.post("/api/chat", json={"thread_id": "11111111-1111-4111-8111-111111111111", "message": text}))


def usage_events(stream):
    return [e for e in stream if e["type"] == "usage"]


def test_each_model_call_of_a_turn_is_a_row_and_the_costs_sum():
    store = FakeStore()
    stream = ask(client([priced(tool_calls=[SEARCH], cost=0.002), priced("A reed.", cost=0.003)], Ledger(store, Budget(1, 4))))
    assert [u.purpose for _, _, u in store.rows] == ["answer", "answer"]
    assert len({r for _, r, _ in store.rows}) == 1 and {t for t, _, _ in store.rows} == {"11111111-1111-4111-8111-111111111111"}
    last = usage_events(stream)[-1]
    assert last["cost"] == 0.005 and last["totalSpend"] == 0.005
    assert last["promptTokens"] == 20 and last["completionTokens"] == 10 and last["warning"] is False
    assert stream[-1] == {"type": "done"}


def test_total_spend_counts_earlier_requests_and_the_turn_cost_does_not():
    store = FakeStore([("old", uuid.uuid4(), Usage("answer", "m", cost=0.5))])
    stream = ask(client([priced("Hi", cost=0.1)], Ledger(store, Budget(1, 4))))
    assert usage_events(stream)[-1]["cost"] == 0.1 and usage_events(stream)[-1]["totalSpend"] == 0.6


def test_rewrite_and_embed_calls_in_a_request_share_its_request_id():
    store = FakeStore()
    stream = ask(client([priced(tool_calls=[SEARCH]), priced("A reed.")], Ledger(store, Budget(1, 4)), retriever=EmbeddingRetriever()))
    assert sorted(u.purpose for _, _, u in store.rows) == ["answer", "answer", "embed"]
    assert len({r for _, r, _ in store.rows}) == 1
    embed_row = next(u for _, _, u in store.rows if u.purpose == "embed")
    assert embed_row.cost == 0.0001
    # the usage event after the tool result already includes the embedding
    assert [e["cost"] for e in usage_events(stream)] == [0.001, 0.0011, 0.0021]


class EmbeddingRetriever(FakeRetriever):
    def __init__(self):
        super().__init__([chunk()])

    def retrieve(self, query, k=5, filters=None):
        record_usage(Usage("embed", "embed/model", 7, 0, 0.0001))
        return super().retrieve(query, k, filters)


def test_rewrite_call_is_recorded_through_the_rewriter():
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    from app.rag.rewrite import Rewrites, make_rewriter

    class RewriteModel(GenericFakeChatModel):
        def with_structured_output(self, schema, **kwargs):
            return self

        def invoke(self, prompt, config=None, **kwargs):
            for callback in config["callbacks"]:
                from langchain_core.outputs import ChatGeneration, LLMResult

                callback.on_llm_end(LLMResult(generations=[[ChatGeneration(message=priced(cost=0.0004))]]))
            return Rewrites(queries=["reed"])

    store = FakeStore()
    from app.db.usage import open_scope

    open_scope(store, "t", rid := uuid.uuid4())
    assert make_rewriter(RewriteModel(messages=iter([])))("clarinet") == ["reed"]
    assert [(r, u.purpose, u.cost) for _, r, u in store.rows] == [(rid, "rewrite", 0.0004)]


def test_a_failing_write_is_logged_and_the_stream_goes_on(caplog):
    store = FakeStore(fail_writes=True)
    stream = ask(client([priced("Hi")], Ledger(store, Budget(1, 4))))
    assert "".join(e["text"] for e in stream if e["type"] == "token").strip() == "Hi"
    assert stream[-1] == {"type": "done"} and "could not write usage_log" in caplog.text


def test_soft_cap_sets_the_warning_flag():
    store = FakeStore([("old", uuid.uuid4(), Usage("answer", "m", cost=0.5))])
    stream = ask(client([priced("Hi", cost=0.1)], Ledger(store, Budget(0.05, 4))))
    assert usage_events(stream)[-1]["warning"] is True


def test_hard_cap_refuses_without_any_model_or_retriever_call_or_row():
    store = FakeStore([("old", uuid.uuid4(), Usage("answer", "m", cost=0.5))])
    app = FastAPI()
    app.include_router(chat.router)
    app.state.agent = Boom()
    app.state.ledger = Ledger(store, Budget(0.1, 0.5))
    stream = events(TestClient(app).post("/api/chat", json={"thread_id": "11111111-1111-4111-8111-111111111111", "message": "hi"}))
    assert [e["type"] for e in stream] == ["usage", "error"]
    assert stream[1]["code"] == "budget_exceeded" and stream[0]["totalSpend"] == 0.5 and stream[0]["warning"] is True
    assert len(store.rows) == 1


def test_default_caps_are_one_and_four():
    from app.config import Settings

    assert (Settings.model_fields["budget_soft_credits"].default, Settings.model_fields["budget_hard_credits"].default) == (1.0, 4.0)


def test_a_failed_turn_still_reports_what_it_spent():
    class FailsAfterToolCall(PricedModel):
        def _stream(self, messages, *args, **kwargs):
            if len(messages) > 2:
                raise RuntimeError("provider down")
            yield from super()._stream(messages, *args, **kwargs)

    store = FakeStore()
    stream = ask(client([priced(tool_calls=[SEARCH], cost=0.002)], Ledger(store, Budget(1, 4)), model_class=FailsAfterToolCall))
    assert [e["type"] for e in stream][-2:] == ["usage", "error"]
    assert stream[-2]["cost"] == 0.002


def test_streamed_chunk_keeps_the_cost():
    """Decision 46: langchain-openai drops usage.cost on streamed chunks, the subclass keeps it."""
    model = CostChatOpenAI(model="x", api_key="k", base_url="http://localhost")
    raw = {
        "id": "gen-1", "choices": [], "model": "openai/gpt-4o-mini",
        "usage": {"prompt_tokens": 72, "completion_tokens": 19, "total_tokens": 91, "cost": 2.22e-05},
    }
    from langchain_core.messages import AIMessageChunk

    generation = model._convert_chunk_to_generation_chunk(raw, AIMessageChunk, {})
    assert generation.message.response_metadata["token_usage"]["cost"] == 2.22e-05
    assert generation.message.usage_metadata["input_tokens"] == 72


def test_a_doubled_model_name_from_streaming_is_repaired():
    from app.db.usage import usage_of_message

    message = priced()
    message.response_metadata["model_name"] = "openai/gpt-4o-miniopenai/gpt-4o-mini"
    assert usage_of_message("answer", message).model == "openai/gpt-4o-mini"
    assert usage_of_message("answer", AIMessage("x")).model == "unknown"
