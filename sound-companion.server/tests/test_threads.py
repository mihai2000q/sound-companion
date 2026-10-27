import asyncio
import json
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import build_agent
from app.api import chat, threads
from app.db.threads import TITLE_LENGTH, Thread, make_title
from app.limits import RateLimiter
from tests.test_chat_api import StreamingToolModel
from tests.test_search_tool import FakeRetriever, chunk

ID = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"


class FakeStore:
    def __init__(self):
        self.rows: dict[str, Thread] = {}
        self.calls = 0

    def ensure(self, thread_id, title):
        self.calls += 1
        self.rows.setdefault(thread_id, Thread(thread_id, title, datetime(2026, 1, self.calls, tzinfo=timezone.utc)))

    def list(self):
        return sorted(self.rows.values(), key=lambda t: t.created_at, reverse=True)

    def get(self, thread_id):
        return self.rows.get(thread_id)

    def delete(self, thread_id):
        return self.rows.pop(thread_id, None) is not None


def make_client(store, replies=None, limiter=None) -> TestClient:
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, chat.invalid_request)
    app.include_router(chat.router)
    app.include_router(threads.router)
    model = StreamingToolModel(messages=iter(replies or [AIMessage("ok")] * 5), seen=[], bound=[])
    app.state.agent = build_agent(model, FakeRetriever([chunk()]), InMemorySaver())
    app.state.thread_store = store
    if limiter:
        app.state.rate_limiter = limiter
    return TestClient(app)


def post(client, thread_id=ID, message="How does a clarinet work?"):
    return client.post("/api/chat", json={"thread_id": thread_id, "message": message})


def test_title_collapses_whitespace_and_cuts_to_a_fixed_length():
    assert make_title("  What   is\n a\tmode? ") == "What is a mode?"
    long = make_title("word " * 50)
    assert len(long) == TITLE_LENGTH and long.endswith("…")
    assert make_title("x" * TITLE_LENGTH) == "x" * TITLE_LENGTH


def test_first_request_creates_one_row_and_a_second_does_not_change_it():
    store = FakeStore()
    client = make_client(store)
    post(client, message="First question")
    post(client, message="Second question")
    assert list(store.rows) == [ID]
    assert store.rows[ID].title == "First question"


def test_invalid_request_writes_no_row():
    store = FakeStore()
    client = make_client(store)
    assert post(client, thread_id="not-a-uuid").status_code == 422
    assert post(client, message="   ").status_code == 422
    assert store.rows == {}


def test_rate_limited_request_writes_no_row():
    store = FakeStore()
    client = make_client(store, limiter=RateLimiter(limit=1))
    assert post(client, thread_id=ID).status_code == 200
    assert post(client, thread_id=OTHER).status_code == 429
    assert list(store.rows) == [ID]


def test_a_failing_store_does_not_stop_the_request():
    class Broken(FakeStore):
        def ensure(self, thread_id, title):
            raise RuntimeError("db down")

    assert post(make_client(Broken())).status_code == 200


def test_list_is_newest_first_and_empty_without_conversations():
    store = FakeStore()
    client = make_client(store)
    assert client.get("/api/threads").json() == []
    post(client, thread_id=ID, message="Older")
    post(client, thread_id=OTHER, message="Newer")
    found = client.get("/api/threads").json()
    assert [t["thread_id"] for t in found] == [OTHER, ID]
    assert found[0] == {"thread_id": OTHER, "title": "Newer", "created_at": "2026-01-02T00:00:00+00:00"}


# --- read, export, delete -------------------------------------------------------------------------------------------

from app.agent.prompt import SYSTEM_PROMPT
from app.db.usage import Budget, Ledger

UNKNOWN = "33333333-3333-4333-8333-333333333333"


class FakeUsage:
    def __init__(self):
        self.rows = {ID: [{"purpose": "answer", "model": "fake/model", "prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001, "created_at": "2026-01-01T00:00:00+00:00"}]}

    def thread_rows(self, thread_id):
        return self.rows.get(thread_id, [])


def conversation():
    search = AIMessage("", tool_calls=[{"name": "search_knowledge_base", "args": {"query": "clarinet"}, "id": "c1"}])
    chord = AIMessage("", tool_calls=[{"name": "chord_info", "args": {"notes": ["C", "E", "G", "B"]}, "id": "c2"}])
    store = FakeStore()
    client = make_client(store, [search, chord, AIMessage("A reed vibrates")])
    assert post(client, message="How does a clarinet work and what is Cmaj7?").status_code == 200
    client.app.state.ledger = Ledger(FakeUsage(), Budget(1, 4))  # after the chat turn: only the export reads it
    return client, store


def test_read_returns_messages_with_tool_calls_and_citations():
    client, _ = conversation()
    found = client.get(f"/api/threads/{ID}").json()
    messages = found["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "assistant", "assistant"]
    assert messages[0]["text"] == "How does a clarinet work and what is Cmaj7?"
    assert messages[-1]["text"].strip() == "A reed vibrates"
    search, chord = messages[1]["tool_calls"][0], messages[2]["tool_calls"][0]
    assert search["name"] == "search_knowledge_base" and search["args"] == {"query": "clarinet"}
    assert search["citations"] == [
        {"title": "Cor anglais", "section": "Design", "url": "https://example.org/Cor_anglais", "score": 0.831,
         "license": "CC BY-SA 4.0", "content": "Cor anglais\nThe cor anglais is a double reed."}
    ]
    assert chord["name"] == "chord_info" and chord["result"] and chord["citations"] == []


def test_export_is_plain_json_with_messages_citations_tool_calls_and_usage():
    client, _ = conversation()
    response = client.get(f"/api/threads/{ID}/export")
    assert "attachment" in response.headers["content-disposition"]
    data = json.loads(response.text)  # json only
    assert data["format_version"] == 1 and data["thread_id"] == ID and data["title"].startswith("How does")
    calls = [c for m in data["messages"] for c in m.get("tool_calls", [])]
    assert [c["name"] for c in calls] == ["search_knowledge_base", "chord_info"]
    assert all(c["result"] for c in calls)
    assert calls[0]["citations"][0]["url"] == "https://example.org/Cor_anglais"
    assert data["usage"]["calls"][0]["model"] == "fake/model"
    assert data["usage"]["total"] == {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001}


def test_export_has_no_system_prompt_and_no_secrets(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-secret-value")
    client, _ = conversation()
    text = client.get(f"/api/threads/{ID}/export").text
    assert SYSTEM_PROMPT[:80] not in text and "sk-or-secret-value" not in text
    assert "app_logs" not in text and "request_id" not in text


def test_delete_removes_row_and_state_but_not_usage():
    client, store = conversation()
    usage = client.app.state.ledger.store
    assert client.delete(f"/api/threads/{ID}").status_code == 204
    assert client.get("/api/threads").json() == []
    assert client.get(f"/api/threads/{ID}").status_code == 404
    state = asyncio.run(client.app.state.agent.aget_state({"configurable": {"thread_id": ID}}))
    assert not state.values.get("messages")
    assert len(usage.rows[ID]) == 1


def test_unknown_thread_is_404_and_malformed_is_422_without_echo():
    client = make_client(FakeStore())
    for path in ("", "/export"):
        assert client.get(f"/api/threads/{UNKNOWN}{path}").status_code == 404
        assert client.get(f"/api/threads/not-a-uuid{path}").status_code == 422
    assert client.delete(f"/api/threads/{UNKNOWN}").status_code == 404
    assert client.delete("/api/threads/not-a-uuid").status_code == 422
    assert client.get(f"/api/threads/{UNKNOWN}").json() == {"detail": "Conversation not found."}
    assert "not-a-uuid" not in client.get("/api/threads/not-a-uuid").text
