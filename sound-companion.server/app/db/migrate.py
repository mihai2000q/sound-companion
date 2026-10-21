from pathlib import Path

import psycopg

from app.config import settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
LOCK_ID = 7_001_001  # arbitrary, keeps concurrent runners (two backend replicas) from interleaving


def run_migrations() -> list[str]:
    """Apply unapplied migrations in filename order, return the versions applied now."""
    applied_now: list[str] = []
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.stem in done:
                    continue
                with conn.transaction():
                    conn.execute(path.read_text())
                    conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,))
                applied_now.append(path.stem)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
    return applied_now


if __name__ == "__main__":
    applied = run_migrations()
    print(f"applied: {', '.join(applied)}" if applied else "nothing to apply")
