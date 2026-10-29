from app.rag.rerank import Ranking, cut_by_score, make_reranker, pick
from app.rag.rewrite import retrieve_with_rewrites
from tests.test_rewrite import FakeModel, StubRetriever
from tests.test_search_tool import chunk


def scored(id, score, section="Design"):
    found = chunk(section, id)
    found.score = score
    return found


def ids(chunks):
    return [c.id for c in chunks]


def test_cut_keeps_chunks_near_the_best_score():
    chunks = [scored("a", 0.8), scored("b", 0.7), scored("c", 0.5)]
    assert ids(cut_by_score(chunks, 0.85)) == ["a", "b"]
    assert ids(cut_by_score(chunks, 0)) == ["a", "b", "c"]  # off


def test_cut_always_keeps_the_best_chunk():
    assert ids(cut_by_score([scored("a", 0.3), scored("b", 0.2)], 1.0)) == ["a"]
    assert cut_by_score([], 0.9) == []


def test_pick_follows_the_model_order_and_ignores_bad_numbers():
    chunks = [scored("a", 0.9), scored("b", 0.8), scored("c", 0.7)]
    assert ids(pick(chunks, [3, 1, 3, 0, 9], keep=5)) == ["c", "a"]
    assert ids(pick(chunks, [2, 1, 3], keep=2)) == ["b", "a"]


def test_reranker_keeps_what_the_model_names():
    chunks = [scored("a", 0.9), scored("b", 0.8), scored("c", 0.7)]
    model = FakeModel(Ranking(relevant=[2, 3]))
    assert ids(make_reranker(model, keep=5)("question?", chunks)) == ["b", "c"]
    assert "question?" in model.prompts[0] and "[1] Cor anglais > Design" in model.prompts[0]


def test_reranker_falls_back_to_retrieval_order_when_the_model_fails_or_names_nothing():
    chunks = [scored("a", 0.9), scored("b", 0.8), scored("c", 0.7)]
    assert ids(make_reranker(FakeModel(error=RuntimeError("boom")), keep=2)("q", chunks)) == ["a", "b"]
    assert ids(make_reranker(FakeModel(Ranking(relevant=[])), keep=2)("q", chunks)) == ["a", "b"]
    assert ids(make_reranker(FakeModel(Ranking(relevant=[7])), keep=2)("q", chunks)) == ["a", "b"]


def test_reranker_makes_no_call_for_one_chunk():
    model = FakeModel(error=RuntimeError("must not be called"))
    assert ids(make_reranker(model, keep=5)("q", [scored("a", 0.9)])) == ["a"]


def test_retrieval_fetches_a_pool_then_trims_to_k():
    class Recording(StubRetriever):
        def retrieve(self, query, k=5, filters=None):
            self.k = k
            return super().retrieve(query, k, filters)

    inner = Recording({"q": [scored("a", 0.9), scored("b", 0.8), scored("c", 0.4)]})
    _, plain = retrieve_with_rewrites(inner, None, "q", 2, None)
    assert inner.k == 2 and ids(plain) == ["a", "b"]  # nothing changes without a reranker or a cut

    _, cut = retrieve_with_rewrites(inner, None, "q", 5, None, pool=10, score_ratio=0.85)
    assert inner.k == 10 and ids(cut) == ["a", "b"]

    def keep_last(query, chunks):
        return chunks[::-1]

    _, reranked = retrieve_with_rewrites(inner, None, "q", 2, None, reranker=keep_last, pool=10)
    assert inner.k == 10 and ids(reranked) == ["c", "b"]
