import uuid

import pytest
from langchain_core.documents import Document
from sqlalchemy import create_engine, text

from app.config import settings
from app.rag.vector_store import ensure_keyword_index

from tests.conftest import TABLE


@pytest.fixture
def keyword_store(store):
    ensure_keyword_index(TABLE)
    return store


def tsv(chunk_id: str) -> str:
    engine = create_engine(settings.database_url_async)
    try:
        with engine.connect() as connection:
            return connection.execute(
                text(f"SELECT content_tsv::text FROM {TABLE} WHERE langchain_id = :id"), {"id": chunk_id}
            ).scalar_one()
    finally:
        engine.dispose()


def test_library_insert_and_upsert_fill_and_update_the_generated_column(keyword_store, request):
    chunk_id = str(uuid.uuid4())
    # the table is shared with the retriever tests, so the row goes again whatever happens
    request.addfinalizer(lambda: keyword_store.delete(ids=[chunk_id]))
    metadata = {"title": "Tsv test", "source_type": "encyclopedia", "url": "https://example.org/t"}
    keyword_store.add_documents([Document(page_content="clarinets play", metadata=metadata)], ids=[chunk_id])
    assert "clarinet" in tsv(chunk_id)

    # the library upserts on a repeated id (ON CONFLICT DO UPDATE), as scripts.index does
    keyword_store.add_documents([Document(page_content="oboes play", metadata=metadata)], ids=[chunk_id])
    assert "obo" in tsv(chunk_id)
    assert "clarinet" not in tsv(chunk_id)
