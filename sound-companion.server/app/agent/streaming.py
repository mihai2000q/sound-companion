"""Turns an agent run into the typed events of the SSE contract (docs/ARCHITECTURE.md). No FastAPI in here."""

import logging
import time
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

logger = logging.getLogger(__name__)

ERROR_MESSAGE = "Something went wrong while answering. Please try again."


def text_of(content: str | list) -> str:
    """Text of a message's content. Real providers may send a list of content blocks."""
    if isinstance(content, str):
        return content
    return "".join(block if isinstance(block, str) else block.get("text", "") for block in content)


def token_events(data) -> list[dict]:
    chunk, metadata = data
    if not isinstance(chunk, AIMessageChunk) or metadata.get("langgraph_node") != "model":
        return []
    text = text_of(chunk.content)
    return [{"type": "token", "text": text}] if text else []


def update_events(data: dict, started: dict[str, float]) -> list[dict]:
    """`started` maps a tool call id to its start time, so the result can carry `durationMs`."""
    events = []
    messages = [m for update in data.values() if isinstance(update, dict) for m in update.get("messages", [])]
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                started[call["id"]] = time.monotonic()
                events.append({"type": "tool_call", "id": call["id"], "name": call["name"], "args": call["args"]})
        elif isinstance(message, ToolMessage):
            began = started.pop(message.tool_call_id, time.monotonic())
            events.append(
                {
                    "type": "tool_result",
                    "id": message.tool_call_id,
                    "name": message.name,
                    "content": text_of(message.content),
                    "durationMs": round((time.monotonic() - began) * 1000),
                }
            )
    return events


async def agent_events(agent, thread_id: str, message: str) -> AsyncIterator[dict]:
    """Yield the events of one turn, ending with `done`, or with `error` when the run fails."""
    started: dict[str, float] = {}
    stream = agent.astream(
        {"messages": [{"role": "user", "content": message}]},
        {"configurable": {"thread_id": thread_id}},
        stream_mode=["messages", "updates", "custom"],
    )
    try:
        async for mode, data in stream:
            if mode == "messages":
                events = token_events(data)
            elif mode == "updates":
                events = update_events(data, started)
            else:  # custom: dicts written by tools with get_stream_writer()
                events = [data] if isinstance(data, dict) and "type" in data else []
            for event in events:
                yield event
    except Exception:
        logger.exception("agent run failed (thread %s)", thread_id)
        yield {"type": "error", "code": "agent_error", "message": ERROR_MESSAGE}
        return
    yield {"type": "done"}
