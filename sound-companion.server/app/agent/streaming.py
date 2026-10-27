"""Turns an agent run into the typed events of the SSE contract (docs/ARCHITECTURE.md). No FastAPI in here."""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from app.db.usage import Ledger, open_scope, record_usage, usage_of_message

logger = logging.getLogger(__name__)

ERROR_MESSAGE = "Something went wrong while answering. Please try again."
CANCELLED = "This tool call was cancelled before it finished, so there is no result."


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


async def cancelled_tool_results(agent, config: dict) -> list[ToolMessage]:
    """A stopped run can leave a tool call without its result, and providers reject such a history.
    These messages answer the dangling calls, and go in front of the next user message."""
    messages = (await agent.aget_state(config)).values.get("messages", [])
    last = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    if last is None:
        return []
    answered = {m.tool_call_id for m in messages[messages.index(last) + 1 :] if isinstance(m, ToolMessage)}
    return [
        ToolMessage(content=CANCELLED, tool_call_id=call["id"], name=call["name"])
        for call in last.tool_calls
        if call["id"] not in answered
    ]


def model_calls(data: dict) -> list[AIMessage]:
    """The AI messages of an `updates` chunk: one per finished call of the answer model."""
    return [
        m for update in data.values() if isinstance(update, dict) for m in update.get("messages", [])
        if isinstance(m, AIMessage)
    ]


async def agent_events(agent, thread_id: str, message: str, ledger: Ledger | None = None) -> AsyncIterator[dict]:
    """Yield the events of one turn, ending with `done`, or with `error` when the run fails.
    With a `ledger` every model call is written to `usage_log`."""
    started: dict[str, float] = {}
    request_id = uuid.uuid4()
    config = {"configurable": {"thread_id": thread_id}}
    try:
        if ledger is not None:
            open_scope(ledger.store, thread_id, request_id)
        repair = await cancelled_tool_results(agent, config)
    except Exception:
        logger.exception("could not read thread %s", thread_id)
        yield {"type": "error", "code": "agent_error", "message": ERROR_MESSAGE}
        return
    stream = agent.astream(
        {"messages": [*repair, {"role": "user", "content": message}]},
        config,
        stream_mode=["messages", "updates", "custom"],
    )
    try:
        async for mode, data in stream:
            if mode == "messages":
                events = token_events(data)
            elif mode == "updates":
                events = update_events(data, started)
                if ledger is not None:
                    for call in model_calls(data):
                        await asyncio.to_thread(record_usage, usage_of_message("answer", call))
            else:  # custom: dicts written by tools with get_stream_writer()
                events = [data] if isinstance(data, dict) and "type" in data else []
            for event in events:
                yield event
    except Exception:
        logger.exception("agent run failed (thread %s)", thread_id)
        yield {"type": "error", "code": "agent_error", "message": ERROR_MESSAGE}
        return
    yield {"type": "done"}
