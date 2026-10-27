"""Scan the stored documents' chunks for instruction-like strings and write an `injection_flag` row per hit.
Run from the server folder: `uv run python -m scripts.scan_injection [--dry-run]`.

Reports only: nothing is deleted or edited. A row holds the chunk id, document, section, pattern and the matched
snippet, never the whole chunk. A chunk and pattern already flagged are not written again, so re-running is safe.
Calls no model.
"""

import argparse
from collections import Counter

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.logs import SqlLogWriter, write_log
from app.db.models import AppLog, DocumentRecord
from app.rag.chunking import chunk_document
from app.rag.injection_scan import Hit, scan_chunks


def flag_data(hit: Hit) -> dict:
    return {
        "chunk_id": hit.chunk_id, "document_id": hit.document_id, "title": hit.title,
        "section": hit.section, "pattern": hit.pattern, "snippet": hit.snippet,
    }


def unflagged(hits: list[Hit], flagged: set[tuple[str | None, str | None]]) -> list[Hit]:
    """The hits whose chunk and pattern have no `injection_flag` row yet."""
    return [hit for hit in hits if (hit.chunk_id, hit.pattern) not in flagged]


def main(dry_run: bool) -> None:
    engine = create_engine(settings.database_url_async)
    with Session(engine) as session:
        documents = session.scalars(select(DocumentRecord).order_by(DocumentRecord.id)).all()
        chunks = [chunk for doc in documents for chunk in chunk_document(doc)]
        flagged = {
            (data.get("chunk_id"), data.get("pattern"))
            for data in session.scalars(select(AppLog.data).where(AppLog.event == "injection_flag"))
        }
    hits = scan_chunks(chunks)
    print(f"{len(documents)} documents, {len(chunks)} chunks scanned")
    for hit in hits:
        place = f"{hit.title} > {hit.section}" if hit.section else hit.title
        print(f"  [{hit.pattern}] {place}: ...{hit.snippet}...")
    print(f"{len(hits)} hits in {len({h.chunk_id for h in hits})} chunks: {dict(Counter(h.pattern for h in hits))}")
    if not dry_run:
        writer = SqlLogWriter(engine)
        new = unflagged(hits, flagged)
        for hit in new:
            write_log(writer, None, "warn", "injection_flag", **flag_data(hit))  # no request: an ingestion-time flag
        print(f"{len(new)} new injection_flag rows written, {len(hits) - len(new)} already flagged")
    engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the report and write no rows")
    main(parser.parse_args().dry_run)
