"""Split every stored document into chunks and print the count, the size spread and a sample.
Run from the server folder: `uv run python -m scripts.chunk [--sample "Cor anglais"]`.

Calls no model and stores nothing. Embedding and indexing come in the next stories.
"""

import argparse
import statistics

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DocumentRecord
from app.rag.chunking import chunk_document


def main(sample_title: str, sample_count: int) -> None:
    engine = create_engine(settings.database_url_async)
    with Session(engine) as session:
        documents = session.scalars(select(DocumentRecord).order_by(DocumentRecord.id)).all()
    chunks = [(doc.title, chunk_document(doc)) for doc in documents]  # a title can repeat
    engine.dispose()

    sizes = [len(c.content) for _, per_doc in chunks for c in per_doc]
    empty = [title for title, per_doc in chunks if not per_doc]
    print(f"{len(documents)} documents -> {len(sizes)} chunks")
    print(
        f"chars per chunk (title line included): min {min(sizes)}, median {statistics.median(sizes):.0f}, "
        f"mean {statistics.mean(sizes):.0f}, max {max(sizes)}"
    )
    print(f"documents without chunks: {len(empty)}" + (f" ({', '.join(empty)})" if empty else ""))

    shown = [c for title, per_doc in chunks if title == sample_title for c in per_doc]
    if not shown:
        print(f"\nNo stored document titled '{sample_title}'.")
        return
    print(f"\n'{sample_title}': {len(shown)} chunks, first {min(sample_count, len(shown))}")
    for chunk in shown[:sample_count]:
        print(f"\n--- {chunk.id} section: {chunk.metadata['section'] or '(lead)'} ({len(chunk.content)} chars)")
        print(chunk.content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sample", default="Cor anglais", help="title of the document to print")
    parser.add_argument("--count", type=int, default=3, help="how many of its chunks to print")
    args = parser.parse_args()
    main(args.sample, args.count)
