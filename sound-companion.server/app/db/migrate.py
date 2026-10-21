from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import settings

DB_DIR = Path(__file__).parent
LOCK_ID = 7_001_001  # arbitrary, keeps concurrent runners (two backend replicas) from interleaving
# Versions recorded by the hand-written SQL runner this replaced, newest last.
LEGACY_VERSIONS = {"0001_enable_pgvector": "0001", "0002_documents": "0002"}


def run_migrations() -> None:
    """Upgrade the database to the latest revision."""
    config = Config(str(DB_DIR.parent.parent / "alembic.ini"))
    config.set_main_option("script_location", str(DB_DIR / "migrations"))
    engine = create_engine(settings.database_url_async)
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": LOCK_ID})
        conn.commit()
        try:
            config.attributes["connection"] = conn
            _adopt_legacy_history(config, conn)
            command.upgrade(config, "head")
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
            conn.commit()
    engine.dispose()


def _adopt_legacy_history(config: Config, conn) -> None:
    """A database migrated by the old SQL runner is stamped at its revision, not migrated again."""
    tables = set(inspect(conn).get_table_names())
    if "schema_migrations" not in tables or "alembic_version" in tables:
        return
    applied = [row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))]
    known = [LEGACY_VERSIONS[v] for v in sorted(applied) if v in LEGACY_VERSIONS]
    conn.commit()
    if known:
        command.stamp(config, known[-1])
    conn.execute(text("DROP TABLE schema_migrations"))
    conn.commit()


if __name__ == "__main__":
    run_migrations()
    print("database is at the latest revision")
