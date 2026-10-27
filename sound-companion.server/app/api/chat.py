import json
import uuid
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AfterValidator, BaseModel, StringConstraints
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.agent.request_log import logged_events
from app.agent.streaming import agent_events
from app.limits import MAX_MESSAGE_LENGTH, UUID_PATTERN, RateLimiter, clean_message
from app.db.logs import LogWriter, write_log

router = APIRouter()

KEEPALIVE_SECONDS = 15
SEP = "\n"  # the library defaults to \r\n, the contract is \n\n


class ChatRequest(BaseModel):
    thread_id: Annotated[str, StringConstraints(strip_whitespace=True, pattern=UUID_PATTERN)]
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH), AfterValidator(clean_message)
    ]


async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
    """The default 422 body, without `input` (it would echo a 50,000 character message back) and `ctx`. The refusal is logged."""
    detail = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in error.errors()]
    if (writer := getattr(request.app.state, "log_writer", None)) is not None:
        write_log(writer, uuid.uuid4(), "warn", "input_rejected", fields=[".".join(map(str, d["loc"])) for d in detail])
    return JSONResponse({"detail": detail}, status_code=422)


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
    limiter: RateLimiter | None = getattr(request.app.state, "rate_limiter", None)
    if limiter is not None and (wait := limiter.retry_after()):
        if (writer := getattr(request.app.state, "log_writer", None)) is not None:
            write_log(writer, uuid.uuid4(), "warn", "rate_limit", retry_after=wait)
        raise HTTPException(429, "Too many requests. Please wait a moment and try again.", headers={"Retry-After": str(wait)})
    return EventSourceResponse(
        sse_events(request.app.state.agent, body, getattr(request.app.state, "ledger", None), getattr(request.app.state, "log_writer", None)),
        sep=SEP,
        ping=KEEPALIVE_SECONDS,
        ping_message_factory=lambda: ServerSentEvent(comment="keepalive", sep=SEP),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
