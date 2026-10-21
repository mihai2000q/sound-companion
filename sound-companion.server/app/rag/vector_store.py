from langchain_core.embeddings import Embeddings
from langchain_postgres import Column, PGEngine, PGVectorStore
from sqlalchemy import create_engine, inspect, text

from app.config import settings
from app.rag.chunking import METADATA_COLUMNS

CHUNKS_TABLE = "chunks"
EMBEDDING_DIMENSIONS = 1536  # openai/text-embedding-3-small


def create_chunk_table() -> bool:
    """Create the chunk table with one real TEXT column per metadata field. Returns False when it
    already exists. The library helper raises on an existing table, so check first."""
    sync_engine = create_engine(settings.database_url_async)
    try:
        if inspect(sync_engine).has_table(CHUNKS_TABLE):
            return False
    finally:
        sync_engine.dispose()
    engine = PGEngine.from_connection_string(settings.database_url_async)
    engine.init_vectorstore_table(
        CHUNKS_TABLE,
        EMBEDDING_DIMENSIONS,
        metadata_columns=[Column(name, "TEXT") for name in METADATA_COLUMNS],
    )
    return True


def open_store(embeddings: Embeddings) -> PGVectorStore:
    engine = PGEngine.from_connection_string(settings.database_url_async)
    return PGVectorStore.create_sync(
        engine, embeddings, CHUNKS_TABLE, metadata_columns=METADATA_COLUMNS
    )


def delete_stale_chunks(keep_ids: list[str], document_ids: list[str] | None = None) -> int:
    """Delete chunks whose id is not in `keep_ids`: those of `document_ids`, or of the whole table
    when it is None (a full run, which also removes chunks of documents that left the Corpus).
    Run it after the upsert, so a failed run leaves the old chunks searchable."""
    statement = f"DELETE FROM {CHUNKS_TABLE} WHERE langchain_id <> ALL(CAST(:keep AS uuid[]))"
    params: dict = {"keep": keep_ids}
    if document_ids is not None:
        statement += " AND document_id = ANY(:documents)"
        params["documents"] = document_ids
    engine = create_engine(settings.database_url_async)
    try:
        with engine.begin() as connection:
            return connection.execute(text(statement), params).rowcount
    finally:
        engine.dispose()
