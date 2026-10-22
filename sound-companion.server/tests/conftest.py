import uuid

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from app.rag.chunking import METADATA_COLUMNS

TABLE = "chunks_filter_test"
DIMENSIONS = 8
ROWS = [  # (title, source_type, topics, aliases, section)
    ("Clarinet", "encyclopedia", "|instruments|woodwinds|transposition|", "Bb clarinet|A clarinet", "History"),
    ("Oboe", "encyclopedia", "|instruments|woodwinds|", "", "Design"),
    ("Snare drum", "encyclopedia", "|instruments|percussion|", "", ""),
    ("The sentence", "textbook", "|form|", "", "Phrase length"),
    ("Formal functions", "textbook", "|formal-analysis|", "", ""),  # "form" inside another topic
    ("Normal order", "textbook", "|post-tonal|", "", ""),
]


@pytest.fixture(scope="session")
def store():
    """A throwaway table on the dev database, with fake embeddings, so no model is called."""
    try:
        from langchain_postgres import Column, PGEngine, PGVectorStore

        from app.config import settings

        engine = PGEngine.from_connection_string(settings.database_url_async)
        engine.init_vectorstore_table(
            TABLE, DIMENSIONS, metadata_columns=[Column(name, "TEXT") for name in METADATA_COLUMNS],
            overwrite_existing=True,
        )
    except Exception as error:  # no environment or no database
        pytest.skip(f"database not available: {error}")
    store = PGVectorStore.create_sync(
        engine, DeterministicFakeEmbedding(size=DIMENSIONS), TABLE, metadata_columns=METADATA_COLUMNS
    )
    store.add_documents(
        [
            Document(
                page_content=f"{title} text",
                metadata={name: "" for name in METADATA_COLUMNS} | {
                    "title": title, "source_type": source_type, "topics": topics,
                    "aliases": aliases, "section": section, "url": f"https://example.org/{title}",
                    "license": "CC BY-SA 4.0", "revision_id": "1",
                },
            )
            for title, source_type, topics, aliases, section in ROWS
        ],
        ids=[str(uuid.uuid4()) for _ in ROWS],
    )
    yield store
    engine.drop_table(TABLE)
