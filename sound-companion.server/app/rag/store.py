from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import create_engine, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import DocumentRecord
from app.rag.documents import Document


def topics_column(topics: list[str]) -> str:
    """Pipe-delimited so `$like '%|woodwinds|%'` can filter a TEXT column (docs/DATABASE-SCHEMA.md)."""
    return f"|{'|'.join(topics)}|" if topics else ""


def store_documents(database_url: str, documents: list[Document]) -> tuple[int, int]:
    """Upsert by URL and delete documents that are no longer in the set, in one transaction.

    `database_url` is the SQLAlchemy psycopg style. Returns (stored, removed). Re-running with
    the same documents changes no row count.
    """
    now = datetime.now(timezone.utc)
    rows = [
        {
            "title": doc.title,
            "source_type": doc.source_type,
            "topics": topics_column(doc.topics),
            "aliases": doc.aliases,
            "url": doc.url,
            "license": doc.license,
            "revision_id": doc.revision_id,
            "sections": [asdict(section) for section in doc.sections],
            "fetched_at": doc.fetched_at or now,
            "char_count": doc.char_count,
        }
        for doc in documents
    ]
    engine = create_engine(database_url)
    with Session(engine) as session, session.begin():
        statement = insert(DocumentRecord).values(rows)
        updates = {name: statement.excluded[name] for name in rows[0] if name != "url"}
        session.execute(statement.on_conflict_do_update(index_elements=["url"], set_=updates))
        removed = session.execute(
            delete(DocumentRecord).where(DocumentRecord.url.not_in([row["url"] for row in rows]))
        ).rowcount
    engine.dispose()
    return len(rows), removed
