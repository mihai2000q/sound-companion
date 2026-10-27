"""The `app_logs` writer. Writing never raises: a failed write goes to stderr and the request goes on."""
import logging
import uuid
from typing import Protocol

from sqlalchemy import Engine, create_engine, insert

from app.db.models import AppLog

log = logging.getLogger(__name__)


class LogWriter(Protocol):
    def add(self, request_id: uuid.UUID, level: str, event: str, data: dict) -> None: ...


class SqlLogWriter:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @classmethod
    def from_settings(cls) -> "SqlLogWriter":
        from app.config import settings

        return cls(create_engine(settings.database_url_async, pool_pre_ping=True))

    def add(self, request_id: uuid.UUID, level: str, event: str, data: dict) -> None:
        with self._engine.begin() as conn:
            conn.execute(insert(AppLog).values(request_id=request_id, level=level, event=event, data=data))


def write_log(writer: LogWriter, request_id: uuid.UUID, level: str, event: str, **data) -> None:
    try:
        writer.add(request_id, level, event, data)
    except Exception:
        log.exception("could not write app_logs (%s)", event)
