import json
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import CostChatOpenAI, build_agent
from app.api import chat
from app.db.usage import Ledger, Totals, Usage, record_usage
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


def client(replies, ledger, retriever=None, model_class=PricedModel, rewriter_model=None):
    app = FastAPI()
    app.include_router(chat.router)
    model = model_class(messages=iter(replies), seen=[], bound=[])
    app.state.agent = build_agent(model, retriever or FakeRetriever([chunk()]), InMemorySaver(), rewriter_model)
    app.state.ledger = ledger
    return TestClient(app)


def ask(test_client, text="hi"):
    return events(test_client.post("/api/chat", json={"thread_id": "t", "message": text}))


def test_each_model_call_of_a_turn_is_a_row_and_the_costs_sum():
    store = FakeStore()
    stream = ask(client([priced(tool_calls=[SEARCH], cost=0.002), priced("A reed.", cost=0.003)], Ledger(store)))
    assert [u.purpose for _, _, u in store.rows] == ["answer", "answer"]
    assert len({r for _, r, _ in store.rows}) == 1 and {t for t, _, _ in store.rows} == {"t"}
    assert [u.cost for _, _, u in store.rows] == [0.002, 0.003]
    assert [(u.prompt_tokens, u.completion_tokens, u.model) for _, _, u in store.rows] == [(10, 5, "fake/model")] * 2
    assert stream[-1] == {"type": "done"}


def test_rewrite_and_embed_calls_in_a_request_share_its_request_id():
    store = FakeStore()
    ask(client([priced(tool_calls=[SEARCH]), priced("A reed.")], Ledger(store), retriever=EmbeddingRetriever()))
    assert sorted(u.purpose for _, _, u in store.rows) == ["answer", "answer", "embed"]
    assert len({r for _, r, _ in store.rows}) == 1
    embed_row = next(u for _, _, u in store.rows if u.purpose == "embed")
    assert embed_row.cost == 0.0001


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
    stream = ask(client([priced("Hi")], Ledger(store)))
    assert "".join(e["text"] for e in stream if e["type"] == "token").strip() == "Hi"
    assert stream[-1] == {"type": "done"} and "could not write usage_log" in caplog.text


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
