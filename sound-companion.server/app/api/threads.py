import asyncio
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import Response
from pydantic import AfterValidator, BaseModel, StringConstraints

from app.agent.history import conversation_messages
from app.db.threads import MAX_TITLE_LENGTH
from app.limits import UUID_PATTERN

router = APIRouter()

EXPORT_VERSION = 1
ThreadId = Annotated[str, Path(pattern=UUID_PATTERN)]  # a malformed id is a 422, as in the chat body


def clean_title(text: str) -> str:
    """Whitespace collapsed to single spaces; control characters are refused."""
    text = re.sub(r"\s+", " ", text).strip()
    if any(unicodedata.category(c) == "Cc" for c in text):
        raise ValueError("title must not contain control characters")
    return text


class RenameRequest(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TITLE_LENGTH), AfterValidator(clean_title)]


def thread_store(request: Request):
    store = getattr(request.app.state, "thread_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Conversations are not available.")
    return store


async def known_thread(request: Request, thread_id: str):
    """The `threads` row, or a 404 that is the same for every id we do not hold."""
    try:
        found = await asyncio.to_thread(thread_store(request).get, thread_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="The conversation could not be read.")
    if found is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return found


async def stored_messages(request: Request, thread_id: str) -> list[dict]:
    state = await request.app.state.agent.aget_state({"configurable": {"thread_id": thread_id}})
    return conversation_messages(state.values.get("messages", []))


@router.get("/api/threads")
async def threads(request: Request):
    """The Conversations, newest first."""
    try:
        found = await asyncio.to_thread(thread_store(request).list)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="The conversations could not be read.")
    return [{"thread_id": t.thread_id, "title": t.title, "created_at": t.created_at.isoformat()} for t in found]


@router.get("/api/threads/{thread_id}")
async def read_thread(thread_id: ThreadId, request: Request):
    """The messages of one Conversation, for the sidebar to restore."""
    found = await known_thread(request, thread_id)
    return {"thread_id": found.thread_id, "title": found.title, "messages": await stored_messages(request, thread_id)}


@router.patch("/api/threads/{thread_id}")
async def rename_thread(thread_id: ThreadId, body: RenameRequest, request: Request):
    """Changes the title of a Conversation and answers with its list row."""
    found = await known_thread(request, thread_id)
    try:
        renamed = await asyncio.to_thread(thread_store(request).rename, thread_id, body.title)
    except Exception:
        raise HTTPException(status_code=503, detail="The conversation could not be renamed.")
    if not renamed:  # deleted between the read and the write
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"thread_id": thread_id, "title": body.title, "created_at": found.created_at.isoformat()}


@router.get("/api/threads/{thread_id}/export")
async def export_thread(thread_id: ThreadId, request: Request):
    """A JSON file: messages with their tool calls and Citations, and the usage rows. No system prompt, keys or logs."""
    found = await known_thread(request, thread_id)
    ledger = getattr(request.app.state, "ledger", None)
    try:
        usage = await asyncio.to_thread(ledger.store.thread_rows, thread_id) if ledger is not None else []
    except Exception:
        raise HTTPException(status_code=503, detail="The usage could not be read.")
    body = {
        "format_version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "thread_id": found.thread_id,
        "title": found.title,
        "created_at": found.created_at.isoformat(),
        "messages": await stored_messages(request, thread_id),
        "usage": {
            "calls": usage,
            "total": {
                "prompt_tokens": sum(u["prompt_tokens"] for u in usage),
                "completion_tokens": sum(u["completion_tokens"] for u in usage),
                "cost": sum(u["cost"] for u in usage),
            },
        },
    }
    return Response(
        json.dumps(body, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="sound-companion-{thread_id}.json"'},
    )


@router.delete("/api/threads/{thread_id}", status_code=204)
async def delete_thread(thread_id: ThreadId, request: Request):
    """Removes the row and the checkpoint state. `usage_log` and `app_logs` rows stay."""
    await known_thread(request, thread_id)
    try:
        await request.app.state.agent.checkpointer.adelete_thread(thread_id)
        await asyncio.to_thread(thread_store(request).delete, thread_id)
    except Exception:
        raise HTTPException(status_code=503, detail="The conversation could not be deleted.")
    return Response(status_code=204)
