from decimal import Decimal

import psycopg
from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row

from app.config import settings

router = APIRouter()

DAYS = 14

# straight from `usage_log` (every model call, with OpenRouter's cost in credits), so no migration is needed
SPEND_PER_DAY = """
SELECT created_at::date AS day,
       sum(prompt_tokens)::bigint AS prompt_tokens,
       sum(completion_tokens)::bigint AS completion_tokens,
       sum(cost_credits) AS cost_credits
FROM usage_log
GROUP BY created_at::date
ORDER BY day DESC
LIMIT %s
"""
USAGE_PER_MODEL = """
SELECT purpose, model,
       count(*) AS calls,
       sum(prompt_tokens)::bigint AS prompt_tokens,
       sum(completion_tokens)::bigint AS completion_tokens,
       sum(cost_credits) AS cost_credits
FROM usage_log
GROUP BY purpose, model
ORDER BY cost_credits DESC, purpose, model
"""


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
            spend = await (await conn.execute(SPEND_PER_DAY, (DAYS,))).fetchall()
            models = await (await conn.execute(USAGE_PER_MODEL)).fetchall()
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="The monitoring views could not be read.")
    spent = {str(row["day"]): plain(row) for row in spend}
    empty = {"prompt_tokens": 0, "completion_tokens": 0, "cost_credits": 0.0}
    days = [{**plain(row), **{k: spent.get(str(row["day"]), empty)[k] for k in empty}} for row in daily]
    return {"daily": days, "tools": [plain(row) for row in tools], "models": [plain(row) for row in models]}
