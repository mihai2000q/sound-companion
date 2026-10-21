"""Chunk, embed and store documents. Run from the server folder:
`uv run python -m scripts.index --limit 9 --title "Cor anglais"`.

Takes the first `--limit` stored documents plus every `--title`, or all of them when neither is
given. Chunk ids are deterministic, so a re-run replaces rows instead of adding them. Needs the
chunk table (`scripts.setup_chunks`).
"""

import argparse
import time

from langchain_core.documents import Document
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DocumentRecord
from app.rag.chunking import chunk_document
from app.rag.embeddings import OpenRouterEmbeddings
from app.rag.vector_store import open_store

WRITE_BATCH = 200  # chunks per `add_documents` call, so progress shows and one failure loses little


def main(limit: int | None, titles: list[str]) -> None:
    engine = create_engine(settings.database_url_async)
    with Session(engine) as session:
        query = select(DocumentRecord).order_by(DocumentRecord.id)
        if limit is None and not titles:
            documents = session.scalars(query).all()
        else:
            documents = session.scalars(query.limit(limit or 0)).all() if limit else []
            wanted = {doc.id for doc in documents}
            documents += [
                doc for doc in session.scalars(query.where(DocumentRecord.title.in_(titles)))
                if doc.id not in wanted
            ]
    engine.dispose()

    chunks = [chunk for doc in documents for chunk in chunk_document(doc)]
    print(f"{len(documents)} documents -> {len(chunks)} chunks")

    embeddings = OpenRouterEmbeddings(
        settings.openrouter_api_key, settings.openrouter_base_url, settings.openrouter_embedding_model
    )
    store = open_store(embeddings)
    started = time.monotonic()
    for start in range(0, len(chunks), WRITE_BATCH):
        batch = chunks[start:start + WRITE_BATCH]
        store.add_documents(
            [Document(page_content=c.content, metadata=c.metadata) for c in batch],
            ids=[str(c.id) for c in batch],
        )
        print(f"  stored {min(start + WRITE_BATCH, len(chunks))}/{len(chunks)}")
    print(
        f"Done in {time.monotonic() - started:.1f} s: {embeddings.tokens} tokens, "
        f"cost {embeddings.cost:.6f} credits."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, help="the first N stored documents")
    parser.add_argument("--title", action="append", default=[], help="a document title to include")
    args = parser.parse_args()
    main(args.limit, args.title)
