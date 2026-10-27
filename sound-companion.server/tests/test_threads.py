from datetime import datetime, timezone

from fastapi import FastAPI
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


def make_client(store, replies=None, limiter=None) -> TestClient:
    app = FastAPI()
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
