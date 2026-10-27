import json
import uuid
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import BaseModel, StringConstraints
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.agent.request_log import logged_events
from app.agent.streaming import agent_events
from app.db.logs import LogWriter

router = APIRouter()

MAX_MESSAGE_LENGTH = 4000
KEEPALIVE_SECONDS = 15
SEP = "\n"  # the library defaults to \r\n, the contract is \n\n


class ChatRequest(BaseModel):
    thread_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH)]


async def sse_events(
    agent, body: ChatRequest, ledger=None, log_writer: LogWriter | None = None
) -> AsyncIterator[ServerSentEvent]:
    request_id, failures = uuid.uuid4(), []
    events = agent_events(agent, body.thread_id, body.message, ledger, request_id, failures.append)
    if log_writer is not None:
        events = logged_events(events, log_writer, request_id, body.thread_id, len(body.message), failures)
    async with aclosing(events):  # a disconnect closes the chain now, so `request_end` is written
        async for event in events:
            yield ServerSentEvent(data=json.dumps(event), sep=SEP)


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    return EventSourceResponse(
        sse_events(request.app.state.agent, body, getattr(request.app.state, "ledger", None), getattr(request.app.state, "log_writer", None)),
        sep=SEP,
        ping=KEEPALIVE_SECONDS,
        ping_message_factory=lambda: ServerSentEvent(comment="keepalive", sep=SEP),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
