from dataclasses import dataclass

from langchain_core.embeddings import Embeddings
from langchain_postgres import Column, PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import HNSWIndex, QueryOptions
from sqlalchemy import create_engine, inspect, text

from app.config import settings
from app.rag.chunking import METADATA_COLUMNS

CHUNKS_TABLE = "chunks"
EMBEDDING_DIMENSIONS = 1536  # openai/text-embedding-3-small


@dataclass
class HnswIterative(QueryOptions):
    """`SET LOCAL` options for every dense query. Without `hnsw.iterative_scan`, a selective filter
    on the HNSW index can return fewer rows than asked for, even none (docs/DATABASE-SCHEMA.md)."""

    ef_search: int = 100
    iterative_scan: str = "relaxed_order"
    max_scan_tuples: int = 20_000

    def to_parameter(self) -> list[str]:
        return [
            f"hnsw.ef_search = {self.ef_search}",
            f"hnsw.iterative_scan = {self.iterative_scan}",
            f"hnsw.max_scan_tuples = {self.max_scan_tuples}",
        ]

    def to_string(self) -> str:
        return "; ".join(self.to_parameter())


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


def open_store(embeddings: Embeddings, **engine_options) -> PGVectorStore:
    """`engine_options` go to SQLAlchemy's `create_async_engine` (pool size, connect args)."""
    engine = PGEngine.from_connection_string(settings.database_url_async, **engine_options)
    return PGVectorStore.create_sync(
        engine,
        embeddings,
        CHUNKS_TABLE,
        metadata_columns=METADATA_COLUMNS,
        index_query_options=HnswIterative(),
    )


def ensure_vector_index(store: PGVectorStore) -> bool:
    """Create the HNSW index on the embedding column. Returns False when it already exists."""
    if store.is_valid_index():
        return False
    store.apply_vector_index(HNSWIndex(m=16, ef_construction=64))
    return True


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
