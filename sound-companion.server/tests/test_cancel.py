import asyncio
import time

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import build_agent
from app.agent.streaming import CANCELLED, agent_events
from tests.test_chat_api import StreamingToolModel
from tests.test_search_tool import FakeRetriever, chunk

CALL = AIMessage("", tool_calls=[{"name": "search_knowledge_base", "args": {"query": "clarinet"}, "id": "c1"}])
CONFIG = {"configurable": {"thread_id": "t"}}


class SlowRetriever(FakeRetriever):
    def retrieve(self, *args, **kwargs):
        time.sleep(0.3)
        return super().retrieve(*args, **kwargs)


def make_agent(replies, retriever=None):
    model = StreamingToolModel(messages=iter(replies), seen=[], bound=[])
    return model, build_agent(model, retriever or FakeRetriever([chunk()]), InMemorySaver())


async def run_turn(agent, text, stop_after=None):
    """Run a turn, stopping early (as a client disconnect does) once an event of that type arrives."""
    seen = []
    stream = agent_events(agent, "t", text)
    try:
        async for event in stream:
            seen.append(event["type"])
            if event["type"] == stop_after:
                break
    finally:
        await stream.aclose()
    return seen


def shape(messages):
    return [m.type for m in messages if m.type != "system"]


def test_dangling_tool_call_gets_a_cancelled_result_before_the_next_question():
    model, agent = make_agent([AIMessage("the oboe is a double reed")])

    async def scenario():
        # what a stopped run can leave: a question and a tool call with no result
        await agent.aupdate_state(CONFIG, {"messages": [HumanMessage("clarinet?"), CALL]}, as_node="tools")
        return await run_turn(agent, "and the oboe?")

    assert asyncio.run(scenario())[-1] == "done"
    history = model.seen[-1]
    assert shape(history) == ["human", "ai", "tool", "human"]
    assert history[3].tool_call_id == "c1" and history[3].content == CANCELLED


def test_thread_continues_after_a_run_stopped_while_a_tool_runs():
    model, agent = make_agent([CALL, AIMessage("second answer")], SlowRetriever([chunk()]))

    async def scenario():
        assert await run_turn(agent, "clarinet?", stop_after="tool_call") == ["tool_call"]
        events = await run_turn(agent, "and the oboe?")
        return events, (await agent.aget_state(CONFIG)).values["messages"]

    events, saved = asyncio.run(scenario())
    assert events[-1] == "done"
    assert saved[-1].content.strip() == "second answer"
    # every tool call in the thread is followed by its result
    for index, message in enumerate(saved):
        for call in getattr(message, "tool_calls", None) or []:
            assert any(m.type == "tool" and m.tool_call_id == call["id"] for m in saved[index + 1 :])
