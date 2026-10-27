"""Turns an agent run into the typed events of the SSE contract (docs/ARCHITECTURE.md). No FastAPI in here."""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from app.limits import MAX_TOOL_CALLS
from app.db.usage import Ledger, open_scope, record_usage, usage_of_message

logger = logging.getLogger(__name__)

ERROR_MESSAGE = "Something went wrong while answering. Please try again."
TOOL_LIMIT_MESSAGE = "This question needed too many steps, so it was stopped. Please ask something simpler."
BUDGET_MESSAGE = "The spending limit for this app has been reached, so no more questions can be answered."
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


async def usage_event(ledger: Ledger, request_id: uuid.UUID) -> dict | None:
    """Tokens and cost of this request so far, and the database sum of all spend. None when it cannot be read."""
    try:
        turn, total = await asyncio.gather(
            asyncio.to_thread(ledger.store.request_totals, request_id), asyncio.to_thread(ledger.store.total_spend)
        )
    except Exception:
        logger.exception("could not read usage")
        return None
    return {
        "type": "usage",
        "promptTokens": turn.prompt_tokens,
        "completionTokens": turn.completion_tokens,
        "cost": turn.cost,
        "totalSpend": total,
        "warning": ledger.budget.warns(total),
    }


async def agent_events(
    agent, thread_id: str, message: str, ledger: Ledger | None = None,
    request_id: uuid.UUID | None = None, on_failure: Callable[[str], None] = lambda text: None,
) -> AsyncIterator[dict]:
    """Yield the events of one turn, ending with `done`, or with `error` when the run fails.
    With a `ledger` the turn is refused at the hard cap (no model call), every model call is written to
    `usage_log`, and `usage` events carry the turn's cost so far and the total spend. `request_id` ties the
    rows of other tables to this turn (made here when not given), `on_failure` gets the exception text, which
    the events never carry."""
    started: dict[str, float] = {}
    request_id = request_id or uuid.uuid4()
    config = {"configurable": {"thread_id": thread_id}}
    try:
        if ledger is not None:
            spend = await asyncio.to_thread(ledger.store.total_spend)
            if ledger.budget.refuses(spend):
                logger.warning("request refused: spend %s is at the hard cap %s", spend, ledger.budget.hard)
                yield {"type": "usage", "promptTokens": 0, "completionTokens": 0, "cost": 0, "totalSpend": spend, "warning": True}
                yield {"type": "error", "code": "budget_exceeded", "message": BUDGET_MESSAGE}
                return
            open_scope(ledger.store, thread_id, request_id)
        repair = await cancelled_tool_results(agent, config)
    except Exception as error:
        logger.exception("could not read thread %s", thread_id)
        on_failure(repr(error))
        yield {"type": "error", "code": "agent_error", "message": ERROR_MESSAGE}
        return
    stream = agent.astream(
        {"messages": [*repair, {"role": "user", "content": message}]},
        config,
        stream_mode=["messages", "updates", "custom"],
    )
    tool_calls = 0
    try:
        async for mode, data in stream:
            if mode == "messages":
                events = token_events(data)
            elif mode == "updates":
                events = update_events(data, started)
                tool_calls += sum(event["type"] == "tool_call" for event in events)
                if tool_calls > MAX_TOOL_CALLS:  # stop before the tools of this step run
                    logger.warning("tool call limit reached (thread %s)", thread_id)
                    await stream.aclose()
                    yield {"type": "error", "code": "tool_limit", "message": TOOL_LIMIT_MESSAGE}
                    return
                if ledger is not None:
                    calls = model_calls(data)
                    for call in calls:
                        await asyncio.to_thread(record_usage, usage_of_message("answer", call))
                    # after a model call, and after a tool result (a search can spend on a rewrite and an embedding)
                    if calls or any(event["type"] == "tool_result" for event in events):
                        usage = await usage_event(ledger, request_id)
                        events = [*events, usage] if usage else events
            else:  # custom: dicts written by tools with get_stream_writer()
                events = [data] if isinstance(data, dict) and "type" in data else []
            for event in events:
                yield event
    except Exception as error:
        logger.exception("agent run failed (thread %s)", thread_id)
        on_failure(repr(error))
        if ledger is not None and (usage := await usage_event(ledger, request_id)):
            yield usage  # a failed turn still shows what it spent
        yield {"type": "error", "code": "agent_error", "message": ERROR_MESSAGE}
        return
    yield {"type": "done"}
