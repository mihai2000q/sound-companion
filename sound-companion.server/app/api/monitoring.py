from decimal import Decimal

import psycopg
from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row

from app.config import settings

router = APIRouter()

DAYS = 14


def plain(row: dict) -> dict:
    """JSON-ready: dates as text, numerics as numbers."""
    return {k: float(v) if isinstance(v, Decimal) else str(v) if k == "day" else v for k, v in row.items()}


@router.get("/api/monitoring")
async def monitoring():
    """Read-only numbers from the monitoring views (migration 0006): the last days, and every tool."""
    try:
        async with await psycopg.AsyncConnection.connect(
            settings.database_url, connect_timeout=3, row_factory=dict_row
        ) as conn:
            daily = await (await conn.execute("SELECT * FROM monitoring_daily ORDER BY day DESC LIMIT %s", (DAYS,))).fetchall()
            tools = await (await conn.execute("SELECT * FROM monitoring_tools ORDER BY calls DESC, tool")).fetchall()
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="The monitoring views could not be read.")
    return {"daily": [plain(row) for row in daily], "tools": [plain(row) for row in tools]}
