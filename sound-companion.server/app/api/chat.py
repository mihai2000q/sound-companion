import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import BaseModel, StringConstraints
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.agent.streaming import agent_events

router = APIRouter()

MAX_MESSAGE_LENGTH = 4000
KEEPALIVE_SECONDS = 15
SEP = "\n"  # the library defaults to \r\n, the contract is \n\n


class ChatRequest(BaseModel):
    thread_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH)]


async def sse_events(agent, body: ChatRequest, ledger=None) -> AsyncIterator[ServerSentEvent]:
    async for event in agent_events(agent, body.thread_id, body.message, ledger):
        yield ServerSentEvent(data=json.dumps(event), sep=SEP)


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    return EventSourceResponse(
        sse_events(request.app.state.agent, body, getattr(request.app.state, "ledger", None)),
        sep=SEP,
        ping=KEEPALIVE_SECONDS,
        ping_message_factory=lambda: ServerSentEvent(comment="keepalive", sep=SEP),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
