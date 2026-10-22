from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


@asynccontextmanager
async def open_checkpointer(url: str | None = None) -> AsyncIterator[AsyncPostgresSaver]:
    """A saver on its own pool. `setup()` creates the library's tables (safe to repeat), Alembic ignores them.
    The saver needs the plain psycopg URL, and a pool with `autocommit`, `prepare_threshold=0` and `dict_row`."""
    if url is None:
        from app.config import settings

        url = settings.database_url
    async with AsyncConnectionPool(
        url,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    ) as pool:
        saver = AsyncPostgresSaver(pool)
        await saver.setup()
        yield saver
