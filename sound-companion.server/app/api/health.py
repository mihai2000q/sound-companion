import psycopg
from fastapi import APIRouter, HTTPException

from app.config import settings

router = APIRouter()


@router.get("/api/health")
async def health():
    try:
        async with await psycopg.AsyncConnection.connect(
            settings.database_url, connect_timeout=3
        ) as conn:
            await conn.execute("SELECT 1")
    except psycopg.Error:
        raise HTTPException(status_code=503, detail={"status": "unavailable", "database": "unreachable"})
    return {"status": "ok", "database": "ok"}
