from langchain_core.embeddings import DeterministicFakeEmbedding

from app.rag.filters import combine, topic_filter

DIMENSIONS = 8


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
