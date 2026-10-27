"""The `threads` table: one row per Conversation, written on the first request of a `thread_id` (decision 68)."""
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import ThreadRecord

log = logging.getLogger(__name__)

TITLE_LENGTH = 60


@dataclass(frozen=True)
class Thread:
    thread_id: str
    title: str | None
    created_at: datetime


class ThreadStore(Protocol):
    def ensure(self, thread_id: str, title: str) -> None: ...

    def list(self) -> list[Thread]: ...


def make_title(message: str, length: int = TITLE_LENGTH) -> str:
    """The first user message with whitespace collapsed, cut at `length` characters (an ellipsis counts in the length)."""
    text = re.sub(r"\s+", " ", message).strip()
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


class SqlThreadStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @classmethod
    def from_settings(cls) -> "SqlThreadStore":
        from app.config import settings

        return cls(create_engine(settings.database_url_async, pool_pre_ping=True))

    def ensure(self, thread_id: str, title: str) -> None:
        """Creates the row if there is none. A second request of the thread changes nothing."""
        with self._engine.begin() as conn:
            conn.execute(insert(ThreadRecord).values(thread_id=thread_id, title=title).on_conflict_do_nothing())

    def list(self) -> list[Thread]:
        query = select(ThreadRecord.thread_id, ThreadRecord.title, ThreadRecord.created_at).order_by(
            ThreadRecord.created_at.desc(), ThreadRecord.thread_id
        )
        with self._engine.connect() as conn:
            return [Thread(*row) for row in conn.execute(query)]


def ensure_thread(store: ThreadStore, thread_id: str, message: str) -> None:
    """Never raises: a failed write is logged and the request goes on."""
    try:
        store.ensure(thread_id, make_title(message))
    except Exception:
        log.exception("could not write threads row")
