import pytest

from app.rag.retriever import Filters, RetrievedChunk, VectorRetriever, to_filter


@pytest.fixture
def retriever(store):
    return VectorRetriever(store)


def titles(chunks: list[RetrievedChunk]) -> set[str]:
    return {chunk.title for chunk in chunks}


def test_no_filter_returns_k_chunks_best_first(retriever):
    chunks = retriever.retrieve("clarinet", k=4)
    assert len(chunks) == 4
    assert [c.score for c in chunks] == sorted((c.score for c in chunks), reverse=True)
    assert all(-1 <= c.score <= 1 for c in chunks)  # similarity, not distance


def test_chunks_carry_what_a_citation_needs(retriever):
    chunk = retriever.retrieve("clarinet", k=6, filters=Filters(title="Clarinet"))[0]
    assert chunk.title == "Clarinet"
    assert chunk.section == "History"
    assert chunk.url == "https://example.org/Clarinet"
    assert chunk.license == "CC BY-SA 4.0"
    assert chunk.revision_id == "1"
    assert chunk.source_type == "encyclopedia"
    assert chunk.topics == ["instruments", "woodwinds", "transposition"]
    assert chunk.aliases == ["Bb clarinet", "A clarinet"]
    assert chunk.id and chunk.content


def test_single_topic(retriever):
    found = retriever.retrieve("anything", k=10, filters=Filters(topics=("woodwinds",)))
    assert titles(found) == {"Clarinet", "Oboe"}


def test_any_of_topics(retriever):
    filters = Filters(topics=("percussion", "post-tonal"), topic_match="any")
    assert titles(retriever.retrieve("anything", k=10, filters=filters)) == {"Snare drum", "Normal order"}


def test_all_of_topics(retriever):
    filters = Filters(topics=("woodwinds", "transposition"), topic_match="all")
    assert titles(retriever.retrieve("anything", k=10, filters=filters)) == {"Clarinet"}


def test_source_type_and_title(retriever):
    textbook = retriever.retrieve("anything", k=10, filters=Filters(source_type="textbook"))
    assert titles(textbook) == {"The sentence", "Formal functions", "Normal order"}
    assert titles(retriever.retrieve("anything", k=10, filters=Filters(title="Oboe"))) == {"Oboe"}


def test_filters_combine(retriever):
    filters = Filters(source_type="encyclopedia", topics=("instruments",), title="Snare drum")
    assert titles(retriever.retrieve("anything", k=10, filters=filters)) == {"Snare drum"}
    contradiction = Filters(source_type="textbook", topics=("woodwinds",))
    assert retriever.retrieve("anything", k=10, filters=contradiction) == []


def test_no_match_is_an_empty_list(retriever):
    assert retriever.retrieve("anything", filters=Filters(topics=("no-such-topic",))) == []
    assert retriever.retrieve("anything", filters=Filters(title="No such page")) == []


def test_a_filter_changes_the_results(retriever):
    plain = retriever.retrieve("anything", k=6)
    narrowed = retriever.retrieve("anything", k=6, filters=Filters(source_type="textbook"))
    assert titles(plain) != titles(narrowed)


def test_unknown_source_type_is_refused():
    with pytest.raises(ValueError):
        Filters(source_type="blog")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Filters(topic_match="some")  # type: ignore[arg-type]


def test_empty_filters_narrow_nothing():
    assert to_filter(None) is None
    assert to_filter(Filters()) is None
