"""Writes `app_logs` rows from the events of `agent_events`. A wrapper, so `streaming.py` stays free of writes.
`usage` events are not logged here, `usage_log` owns them."""
import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

from app.db.logs import LogWriter, write_log


def is_error_result(content: str) -> bool:
    """Tools report failures as "Error: ..." text (search) or an `{"error": ...}` object (music tools)."""
    if content.startswith("Error"):
        return True
    try:
        parsed = json.loads(content)
    except ValueError:
        return False
    return isinstance(parsed, dict) and "error" in parsed


async def logged_events(
    events: AsyncIterator[dict], writer: LogWriter, request_id: uuid.UUID, thread_id: str, message_length: int,
    failures: list[str] | None = None,
) -> AsyncIterator[dict]:
    """Pass every event through and write a row for the ones worth keeping. A stopped stream (the client
    disconnected, so this generator is closed or cancelled) still writes `request_end`, synchronously because
    an `await` is not safe while being cancelled. `failures` collects the exception text of the run, which
    goes into the `error` row and never to the client."""
    began = time.monotonic()
    outcome = "stopped"
    chunks: list[dict] = []

    def write(level: str, event: str, **data) -> None:
        write_log(writer, request_id, level, event, **data)

    async def write_async(level: str, event: str, **data) -> None:
        await asyncio.to_thread(write, level, event, **data)

    await write_async("info", "request", thread_id=thread_id, message_length=message_length)
    try:
        async for event in events:
            kind = event["type"]
            if kind == "tool_call":
                await write_async("info", "tool_call", id=event["id"], name=event["name"], args=event["args"])
            elif kind == "tool_result":
                failed = is_error_result(event["content"])
                await write_async(
                    "warn" if failed else "info", "tool_result",
                    id=event["id"], name=event["name"], duration_ms=event["durationMs"], error=failed,
                )
            elif kind == "citations":
                chunks = [{"id": item["id"], "score": item["score"]} for item in event["items"]]
            elif kind == "queries":  # always sent right after `citations`
                await write_async("info", "retrieval", queries=event["items"], chunks=chunks)
            elif kind == "error":
                code = event["code"]
                if code == "budget_exceeded":
                    await write_async("warn", "budget_block")
                else:
                    await write_async("error", "error", code=code, exception="; ".join(failures or []) or None)
                outcome = "error"
            elif kind == "done":
                outcome = "done"
            yield event
    finally:
        write(
            "info", "request_end",
            duration_ms=round((time.monotonic() - began) * 1000), outcome=outcome,
        )
