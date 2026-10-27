import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from app.config import settings
from app.rag.hybrid import HybridRetriever
from app.rag.retriever import Filters, VectorRetriever
from tests.conftest import DIMENSIONS, TABLE

FAKE = DeterministicFakeEmbedding(size=DIMENSIONS)


class SteeredEmbeddings:
    """Embeds a query as another text, so a test says which chunk the dense half finds."""

    def __init__(self, steer: dict[str, str] | None = None) -> None:
        self._steer = steer or {}
        self.cost = 0.25

    def embed_query(self, text: str) -> list[float]:
        return FAKE.embed_query(self._steer.get(text, text))


def make(steer=None, candidates=20) -> HybridRetriever:
    return HybridRetriever(SteeredEmbeddings(steer), settings.database_url, TABLE, candidates)


def titles(chunks) -> list[str]:
    return [chunk.title for chunk in chunks]


@pytest.fixture
def retriever(store):
    return make()


def test_returns_the_fields_of_the_baseline(store, retriever):
    filters = Filters(title="Clarinet")
    hybrid = retriever.retrieve("clarinet", k=3, filters=filters)[0]
    baseline = VectorRetriever(store).retrieve("clarinet", k=3, filters=filters)[0]
    for name in ("id", "content", "title", "section", "url", "license", "revision_id", "source_type",
                 "topics", "aliases"):
        assert getattr(hybrid, name) == getattr(baseline, name)
    assert hybrid.topics == ["instruments", "woodwinds", "transposition"]


def test_keyword_only_vector_only_and_both(store):
    # one candidate per half: the dense half finds only Oboe, the keyword half only Snare drum
    split = make({"snare": "Oboe text"}, candidates=1).retrieve("snare", k=5)
    assert set(titles(split)) == {"Oboe", "Snare drum"}
    assert [c.score for c in split] == [pytest.approx(1 / 61)] * 2
    # a chunk found by both halves ranks first with both ranks added
    steered = {"snare drum": "Snare drum text"}
    both = make(steered | {"oboe": "Snare drum text"}, candidates=1)
    found = both.retrieve("snare drum", k=5)
    assert titles(found) == ["Snare drum"]
    assert found[0].score == pytest.approx(2 / 61)


def test_a_chunk_in_both_halves_outranks_one_in_a_single_half(store):
    # dense candidates: Oboe and its nearest neighbour, keyword candidate: Oboe only
    found = make({"oboe": "Oboe text"}, candidates=2).retrieve("oboe", k=5)
    assert len(found) == 2
    assert titles(found)[0] == "Oboe"
    assert found[0].score == pytest.approx(2 / 61)
    assert found[1].score == pytest.approx(1 / 62)


@pytest.mark.parametrize(
    "filters",
    [
        Filters(source_type="textbook"),
        Filters(title="Oboe"),
        Filters(topics=("woodwinds",)),
        Filters(topics=("percussion", "post-tonal"), topic_match="any"),
        Filters(topics=("woodwinds", "transposition"), topic_match="all"),
        Filters(source_type="encyclopedia", topics=("instruments",), title="Snare drum"),
        Filters(source_type="textbook", topics=("woodwinds",)),
        Filters(topics=("no-such-topic",)),
    ],
)
def test_filters_return_the_rows_of_the_baseline(store, retriever, filters):
    baseline = VectorRetriever(store).retrieve("anything", k=10, filters=filters)
    assert set(titles(retriever.retrieve("anything", k=10, filters=filters))) == set(titles(baseline))


def test_filter_narrows_the_keyword_half_too(retriever):
    # "text" is in every chunk, so only the filter keeps the keyword half to textbook pages
    found = retriever.retrieve("text", k=10, filters=Filters(source_type="textbook"))
    assert set(titles(found)) == {"The sentence", "Formal functions", "Normal order"}


def test_topic_with_a_wildcard_character_matches_nothing(retriever):
    assert retriever.retrieve("anything", filters=Filters(topics=("%",))) == []
    assert retriever.retrieve("anything", filters=Filters(topics=("form_l-analysis",))) == []


def test_stop_words_only_fall_back_to_the_dense_results(store, retriever):
    found = retriever.retrieve("the of and", k=3)
    assert len(found) == 3
    assert titles(found) == titles(VectorRetriever(store).retrieve("the of and", k=3))


def test_cost_is_the_embeddings_cost(retriever):
    assert retriever.embedding_cost == 0.25
