import asyncio
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import build_agent
from app.agent.streaming import agent_events
from app.api import chat
from tests.test_agent import FakeToolModel
from tests.test_search_tool import FakeRetriever, chunk


class NoHistory:
    """The part of an agent that `agent_events` reads before a run: an empty thread."""

    async def aget_state(self, config):
        return type("State", (), {"values": {}})()


class StreamingToolModel(FakeToolModel):
    """The base fake streams nothing for a reply with no text, so a tool call is sent as one chunk."""

    def _stream(self, messages, *args, **kwargs):
        self.seen.append(messages)
        reply = next(self.messages)
        if reply.tool_calls:
            chunks = [
                {"name": c["name"], "args": json.dumps(c["args"]), "id": c["id"], "index": i}
                for i, c in enumerate(reply.tool_calls)
            ]
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=chunks))
        else:
            for word in reply.content.split(" "):
                yield ChatGenerationChunk(message=AIMessageChunk(content=word + " "))


class BrokenModel(StreamingToolModel):
    def _generate(self, messages, *args, **kwargs):
        raise RuntimeError("provider down")

    def _stream(self, messages, *args, **kwargs):
        raise RuntimeError("provider down")


def make_client(replies=None, model_class=StreamingToolModel) -> TestClient:
    app = FastAPI()
    app.include_router(chat.router)
    model = model_class(messages=iter(replies or []), seen=[], bound=[])
    app.state.agent = build_agent(model, FakeRetriever([chunk()]), InMemorySaver())
    return TestClient(app)


def events(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def post(client, **body):
    return client.post("/api/chat", json={"thread_id": "t1", "message": "How does a clarinet work?"} | body)


def test_plain_answer_streams_tokens_then_done():
    response = post(make_client([AIMessage("A reed vibrates")]))
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["content-type"].startswith("text/event-stream")
    found = events(response)
    assert [e["type"] for e in found][-1] == "done"
    assert "".join(e["text"] for e in found if e["type"] == "token") == "A reed vibrates "


def test_search_shows_tool_call_then_tool_result_before_the_answer_tokens():
    call = AIMessage("", tool_calls=[{"name": "search_knowledge_base", "args": {"query": "clarinet"}, "id": "c1"}])
    found = events(post(make_client([call, AIMessage("A reed vibrates")])))
    assert [e["type"] for e in found][:2] == ["tool_call", "tool_result"]
    assert found[0] == {"type": "tool_call", "id": "c1", "name": "search_knowledge_base", "args": {"query": "clarinet"}}
    assert found[1]["id"] == "c1" and found[1]["name"] == "search_knowledge_base"
    assert isinstance(found[1]["durationMs"], int)
    assert [e["type"] for e in found[2:]] == ["token", "token", "token", "done"]


def test_invalid_input_is_422_with_the_field_named_and_no_stream():
    client = make_client([AIMessage("unused")])
    for body, field in (({"message": ""}, "message"), ({"message": "   "}, "message"), ({"thread_id": None}, "thread_id")):
        response = post(client, **body)
        assert response.status_code == 422
        assert not response.headers["content-type"].startswith("text/event-stream")
        assert field in response.json()["detail"][0]["loc"]
    missing = client.post("/api/chat", json={"message": "hi"})
    assert missing.status_code == 422 and "thread_id" in missing.json()["detail"][0]["loc"]


def test_failure_inside_the_run_ends_with_an_error_event():
    found = events(post(make_client(model_class=BrokenModel)))
    assert [e["type"] for e in found] == ["error"]
    assert found[0]["code"] == "agent_error" and "provider down" not in found[0]["message"]


def test_keepalive_comment_is_sent_while_nothing_arrives(monkeypatch):
    class SlowAgent(NoHistory):
        async def astream(self, *args, **kwargs):
            await asyncio.sleep(0.3)
            yield "custom", {"type": "progress", "message": "searching"}

    monkeypatch.setattr(chat, "KEEPALIVE_SECONDS", 0.1)
    app = FastAPI()
    app.include_router(chat.router)
    app.state.agent = SlowAgent()
    text = post(TestClient(app)).text
    assert ": keepalive" in text and text.index(": keepalive") < text.index("progress")


def test_custom_events_with_a_type_are_forwarded():
    class Agent(NoHistory):
        async def astream(self, *args, **kwargs):
            yield "custom", {"type": "progress", "message": "searching"}
            yield "custom", {"no": "type"}

    async def collect():
        return [e async for e in agent_events(Agent(), "t", "hi")]

    assert asyncio.run(collect()) == [{"type": "progress", "message": "searching"}, {"type": "done"}]
