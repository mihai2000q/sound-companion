import asyncio

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/api/threads")
async def threads(request: Request):
    """The Conversations, newest first."""
    store = getattr(request.app.state, "thread_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Conversations are not available.")
    try:
        found = await asyncio.to_thread(store.list)
    except Exception:
        raise HTTPException(status_code=503, detail="The conversations could not be read.")
    return [{"thread_id": t.thread_id, "title": t.title, "created_at": t.created_at.isoformat()} for t in found]
