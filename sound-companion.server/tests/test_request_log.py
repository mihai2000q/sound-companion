import asyncio
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import build_agent
from app.agent.request_log import is_error_result, logged_events
from app.api import chat
from app.db.usage import Budget, Ledger, Usage
from tests.test_chat_api import StreamingToolModel, events
from tests.test_search_tool import FakeRetriever, chunk
from tests.test_usage import SEARCH, Boom, FakeStore, priced


class FakeWriter:
    def __init__(self, fail=False):
        self.rows: list[tuple[uuid.UUID, str, str, dict]] = []
        self.fail = fail

    def add(self, request_id, level, event, data):
        if self.fail:
            raise RuntimeError("database down")
        self.rows.append((request_id, level, event, data))

    def names(self):
        return [event for _, _, event, _ in self.rows]


def client(replies, writer, ledger=None):
    app = FastAPI()
    app.include_router(chat.router)
    model = StreamingToolModel(messages=iter(replies), seen=[], bound=[])
    app.state.agent = build_agent(model, FakeRetriever([chunk()]), InMemorySaver(), None)
    app.state.log_writer = writer
    if ledger:
        app.state.ledger = ledger
    return TestClient(app)


def post(test_client, text="hi"):
    return events(test_client.post("/api/chat", json={"thread_id": "11111111-1111-4111-8111-111111111111", "message": text}))


def test_a_search_turn_writes_its_rows_under_one_request_id():
    writer = FakeWriter()
    post(client([AIMessage("", tool_calls=[SEARCH]), AIMessage("A reed.")], writer))
    assert writer.names() == ["request", "tool_call", "retrieval", "tool_result", "request_end"]
    assert len({r for r, *_ in writer.rows}) == 1
    by_event = {event: data for _, _, event, data in writer.rows}
    assert by_event["request"] == {"thread_id": "11111111-1111-4111-8111-111111111111", "message_length": 2}
    assert by_event["tool_result"]["name"] == "search_knowledge_base" and by_event["tool_result"]["error"] is False
    assert by_event["retrieval"]["queries"] == ["clarinet"] and by_event["retrieval"]["chunks"][0]["id"] == chunk().id
    assert by_event["request_end"]["outcome"] == "done"


def test_a_refused_request_writes_budget_block_and_calls_no_model():
    writer = FakeWriter()
    app = FastAPI()
    app.include_router(chat.router)
    app.state.agent = Boom()
    app.state.log_writer = writer
    app.state.ledger = Ledger(FakeStore([("old", uuid.uuid4(), Usage("answer", "m", cost=0.5))]), Budget(0.1, 0.5))
    post_events = events(TestClient(app).post("/api/chat", json={"thread_id": "11111111-1111-4111-8111-111111111111", "message": "hi"}))
    assert post_events[-1]["code"] == "budget_exceeded"
    assert writer.names() == ["request", "budget_block", "request_end"]
    assert writer.rows[-1][3]["outcome"] == "error"


def test_an_agent_failure_logs_the_exception_text_only_server_side():
    class Failing(StreamingToolModel):
        def _stream(self, messages, *args, **kwargs):
            raise RuntimeError("provider down")

    writer = FakeWriter()
    app = FastAPI()
    app.include_router(chat.router)
    app.state.agent = build_agent(Failing(messages=iter([]), seen=[], bound=[]), FakeRetriever([chunk()]), InMemorySaver(), None)
    app.state.log_writer = writer
    stream = post(TestClient(app))
    assert "provider down" not in str(stream)
    error = next(data for _, _, event, data in writer.rows if event == "error")
    assert error["code"] == "agent_error" and "provider down" in error["exception"]


def test_a_failing_write_is_logged_and_the_stream_goes_on(caplog):
    stream = post(client([AIMessage("Hi")], FakeWriter(fail=True)))
    assert stream[-1] == {"type": "done"} and "could not write app_logs" in caplog.text


def test_a_stopped_stream_still_writes_request_end():
    async def endless():
        yield {"type": "token", "text": "a"}
        await asyncio.sleep(10)

    async def run():
        writer = FakeWriter()
        stream = logged_events(endless(), writer, uuid.uuid4(), "t", 1)
        await stream.__anext__()  # first token, after the request row
        await stream.aclose()  # the client went away
        return writer

    writer = asyncio.run(run())
    assert writer.names() == ["request", "request_end"] and writer.rows[-1][3]["outcome"] == "stopped"


def test_error_results_are_recognised():
    assert is_error_result("Error: query must not be empty.")
    assert is_error_result('{"error": "invalid_chord", "message": "x"}')
    assert not is_error_result('{"notes": ["C"]}') and not is_error_result("some text")


KEY = "sk-or-v1-0123456789abcdef0123456789abcdef"
SYSTEM_PROMPT = "You are Sound Companion, a patient teacher of music theory. " * 40


def test_a_key_and_a_long_prompt_in_an_error_or_a_tool_call_reach_no_row(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", KEY)

    class Failing(StreamingToolModel):
        def _stream(self, messages, *args, **kwargs):
            raise RuntimeError(f"401 for key {KEY}; request was {SYSTEM_PROMPT}")

    writer = FakeWriter()
    app = FastAPI()
    app.include_router(chat.router)
    app.state.agent = build_agent(Failing(messages=iter([]), seen=[], bound=[]), FakeRetriever([chunk()]), InMemorySaver(), None)
    app.state.log_writer = writer
    post(TestClient(app))
    leaky = {"name": "search_knowledge_base", "args": {"query": f"{SYSTEM_PROMPT} {KEY}"}, "id": "1"}
    from app.db.logs import write_log  # redaction lives in write_log

    write_log(writer, uuid.uuid4(), "info", "tool_call", **leaky)
    text = str(writer.rows)
    assert KEY not in text and SYSTEM_PROMPT not in text and "[redacted]" in text


def test_redact_masks_and_truncates():
    from app.security.redact import MAX_TEXT, redact

    out = redact({"a": ["Bearer abcdefgh12345", "x" * 1000], "n": 3}, secrets=("hunter22",))
    assert out["a"][0] == "[redacted]" and len(out["a"][1]) < MAX_TEXT + 40 and out["n"] == 3
    assert redact("pw hunter22", secrets=("hunter22",)) == "pw [redacted]"
