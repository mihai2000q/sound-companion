import json

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import build_agent
from app.api import chat
from app.limits import MAX_TOOL_CALLS, RateLimiter, clean_message
from tests.test_chat_api import StreamingToolModel, events
from tests.test_request_log import FakeWriter
from tests.test_search_tool import FakeRetriever, chunk

THREAD = "22222222-2222-4222-8222-222222222222"


def make_client(replies, writer=None, limiter=None) -> tuple[TestClient, StreamingToolModel]:
    app = FastAPI()
    app.include_router(chat.router)
    app.add_exception_handler(RequestValidationError, chat.invalid_request)
    model = StreamingToolModel(messages=iter(replies), seen=[], bound=[])
    app.state.agent = build_agent(model, FakeRetriever([chunk()]), InMemorySaver())
    if writer:
        app.state.log_writer = writer
    if limiter:
        app.state.rate_limiter = limiter
    return TestClient(app), model


def post(client, **body):
    return client.post("/api/chat", json={"thread_id": THREAD, "message": "What is a clarinet?"} | body)


def search(i: int) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": "search_knowledge_base", "args": {"query": "q"}, "id": f"c{i}"}])


def test_oversized_message_is_rejected_before_any_model_call():
    client, model = make_client([AIMessage("unused")], writer=(writer := FakeWriter()))
    response = post(client, message="x" * 50_000)
    assert response.status_code == 422
    assert model.seen == []
    assert "xxxx" not in response.text  # the input is not echoed back
    assert writer.names() == ["input_rejected"]


def test_thread_id_must_be_a_uuid_and_control_characters_are_refused():
    client, model = make_client([AIMessage("unused")])
    assert post(client, thread_id="t1").status_code == 422
    assert post(client, message="hi\x00there").status_code == 422
    assert post(client, message="hi\x1b[31m").status_code == 422
    assert model.seen == []


def test_whitespace_is_normalised():
    assert clean_message("  a   b\t c \r\n\r\n\r\n\r\n d  ") == "a b c\n\nd"


def test_tenth_request_succeeds_and_eleventh_gets_429_with_retry_after():
    now = [100.0]
    limiter = RateLimiter(10, 60, clock=lambda: now[0])
    client, model = make_client([AIMessage(f"r{i}") for i in range(11)], writer=(writer := FakeWriter()), limiter=limiter)
    assert [post(client).status_code for _ in range(10)] == [200] * 10
    refused = post(client)
    assert refused.status_code == 429 and int(refused.headers["retry-after"]) == 60
    assert len(model.seen) == 10
    assert "rate_limit" in writer.names()
    now[0] += 61
    assert post(client).status_code == 200


def test_a_model_that_keeps_calling_a_tool_stops_at_the_limit():
    client, model = make_client([search(i) for i in range(100)], writer=(writer := FakeWriter()))
    found = events(post(client))
    assert [e["type"] for e in found].count("tool_call") == MAX_TOOL_CALLS
    assert found[-1]["type"] == "error" and found[-1]["code"] == "tool_limit"
    assert len(model.seen) == MAX_TOOL_CALLS + 1  # the call over the limit is never run
    assert "tool_limit" in writer.names() and "request_end" in writer.names()


def test_a_thread_can_go_on_after_the_limit():
    client, _ = make_client([search(i) for i in range(MAX_TOOL_CALLS + 1)] + [AIMessage("fine")])
    post(client)
    found = events(post(client, message="Try again"))
    assert found[-1]["type"] == "done"
