"""Print everything one request did, in time order: its `app_logs` rows and its `usage_log` rows
(answer, rewrite and embed calls). Run from the server folder:

    uv run python -m scripts.trace <request_id>
"""

import argparse
import json
import uuid

from sqlalchemy import create_engine, select

from app.config import settings
from app.db.models import AppLog, UsageLog


def trace(engine, request_id: uuid.UUID) -> list[tuple]:
    """(time, source, name, detail) for every row of the request, oldest first."""
    with engine.connect() as conn:
        logs = conn.execute(select(AppLog).where(AppLog.request_id == request_id)).all()
        usage = conn.execute(select(UsageLog).where(UsageLog.request_id == request_id)).all()
    rows = [(r.created_at, "app_logs", f"{r.level} {r.event}", json.dumps(r.data)) for r in logs]
    rows += [
        (r.created_at, "usage_log", r.purpose, f"{r.model} in={r.prompt_tokens} out={r.completion_tokens} cost={r.cost_credits}")
        for r in usage
    ]
    return sorted(rows, key=lambda row: row[0])


def main(args: argparse.Namespace) -> None:
    rows = trace(create_engine(settings.database_url_async), args.request_id)
    for when, source, name, detail in rows:
        print(f"{when:%H:%M:%S.%f}  {source:<9}  {name:<16}  {detail}")
    if not rows:
        print("no rows for that request id")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("request_id", type=uuid.UUID)
    main(parser.parse_args())
