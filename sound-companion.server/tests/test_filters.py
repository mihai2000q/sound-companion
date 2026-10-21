import uuid

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from app.rag.chunking import METADATA_COLUMNS
from app.rag.filters import combine, topic_filter

TABLE = "chunks_filter_test"
DIMENSIONS = 8
ROWS = [  # (title, source_type, topics)
    ("Clarinet", "encyclopedia", "|instruments|woodwinds|transposition|"),
    ("Oboe", "encyclopedia", "|instruments|woodwinds|"),
    ("Snare drum", "encyclopedia", "|instruments|percussion|"),
    ("The sentence", "textbook", "|form|"),
    ("Formal functions", "textbook", "|formal-analysis|"),  # contains "form" but is not the topic
    ("Normal order", "textbook", "|post-tonal|"),
]


@pytest.fixture(scope="module")
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
    embeddings = DeterministicFakeEmbedding(size=DIMENSIONS)
    store = PGVectorStore.create_sync(
        engine, embeddings, TABLE, metadata_columns=METADATA_COLUMNS
    )
    store.add_documents(
        [
            Document(
                page_content=f"{title} text",
                metadata={name: "" for name in METADATA_COLUMNS}
                | {"title": title, "source_type": source_type, "topics": topics},
            )
            for title, source_type, topics in ROWS
        ],
        ids=[str(uuid.uuid4()) for _ in ROWS],
    )
    yield store
    engine.drop_table(TABLE)


def titles(store, filter: dict | None) -> set[str]:
    vector = DeterministicFakeEmbedding(size=DIMENSIONS).embed_query("anything")
    return {d.metadata["title"] for d in store.similarity_search_by_vector(vector, k=20, filter=filter)}


def test_single_topic(store):
    assert titles(store, topic_filter(["woodwinds"])) == {"Clarinet", "Oboe"}


def test_topic_does_not_match_a_longer_topic_that_contains_it(store):
    assert titles(store, topic_filter(["form"])) == {"The sentence"}


def test_any_of_topics(store):
    found = titles(store, topic_filter(["percussion", "post-tonal"], "any"))
    assert found == {"Snare drum", "Normal order"}


def test_all_of_topics(store):
    assert titles(store, topic_filter(["woodwinds", "transposition"], "all")) == {"Clarinet"}


def test_no_match_is_an_empty_result(store):
    assert titles(store, topic_filter(["woodwinds", "percussion"], "all")) == set()
    assert titles(store, topic_filter(["no-such-topic"])) == set()


def test_topics_combine_with_source_type_and_title(store):
    textbook = combine(topic_filter(["post-tonal", "form"], "any"), {"source_type": "textbook"})
    assert titles(store, textbook) == {"The sentence", "Normal order"}
    assert titles(store, combine(topic_filter(["instruments"]), {"title": "Oboe"})) == {"Oboe"}


def test_combine_skips_empty_filters():
    assert combine(None, {}) is None
    assert combine(None, {"title": "Oboe"}) == {"title": "Oboe"}
