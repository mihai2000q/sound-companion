from pathlib import Path

import pytest

from app.rag.evaluation import (
    GoldenQuestion,
    UnknownSourceError,
    check_sources,
    corpus_names,
    evaluate,
    is_relevant,
    load_golden_set,
    score,
    summarize,
)
from app.rag.retriever import Filters, RetrievedChunk

NAMES = corpus_names([
    ("Cor anglais", ["English horn"]),
    ("Guitar", ["Acoustic guitar"]),
    ("Oboe", []),
    ("Clarinet", []),
])


def chunk(title: str, aliases: list[str] | None = None) -> RetrievedChunk:
    return RetrievedChunk(id="x", content="", score=0.5, title=title, section="", url="", license="",
                          revision_id="", source_type="encyclopedia", aliases=aliases or [])


def question(sources: list[str], id: str = "q1", behaviour: str = "answer") -> GoldenQuestion:
    return GoldenQuestion(id=id, question="?", category="c", difficulty="easy",
                          expected_sources=sources, expected_behaviour=behaviour)


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks, self.calls = chunks, []

    def retrieve(self, query, k=5, filters=None):
        self.calls.append((query, k, filters))
        return self.chunks[:k]


def test_precision_is_relevant_chunks_over_k_and_recall_is_pages_found():
    top = [chunk("Oboe"), chunk("Oboe"), chunk("Clarinet"), chunk("Guitar"), chunk("Guitar")]
    result = score(question(["Oboe", "Clarinet"]), top, NAMES)
    assert result.precision == 3 / 5
    assert result.recall == 1.0
    assert result.found_pages == ["Oboe", "Clarinet"]


def test_a_missing_page_lowers_recall():
    result = score(question(["Oboe", "Clarinet"]), [chunk("Oboe")] * 5, NAMES)
    assert result.precision == 1.0
    assert result.recall == 0.5
    assert result.found_pages == ["Oboe"]


def test_nothing_relevant_scores_zero():
    result = score(question(["Oboe"]), [chunk("Guitar")] * 5, NAMES)
    assert (result.precision, result.recall) == (0.0, 0.0)


def test_fewer_than_k_results_still_divides_by_k():
    assert score(question(["Oboe"]), [chunk("Oboe"), chunk("Oboe")], NAMES).precision == 2 / 5


def test_only_the_top_k_count():
    chunks = [chunk("Guitar")] * 5 + [chunk("Oboe")]
    assert score(question(["Oboe"]), chunks, NAMES, k=5).recall == 0.0
    assert score(question(["Oboe"]), chunks, NAMES, k=6).recall == 1.0


def test_an_alias_as_expected_source_matches_the_page():
    result = score(question(["English horn"]), [chunk("Cor anglais")] * 5, NAMES)
    assert (result.precision, result.recall) == (1.0, 1.0)
    assert result.expected_pages == ["Cor anglais"]


def test_a_chunk_is_relevant_through_its_own_aliases():
    assert is_relevant(chunk("Something else", aliases=["English horn"]), {"English horn"})
    assert not is_relevant(chunk("Something else"), {"English horn"})


def test_a_title_and_its_alias_expected_together_count_as_one_page():
    result = score(question(["Cor anglais", "English horn"]), [chunk("Cor anglais")] * 5, NAMES)
    assert result.expected_pages == ["Cor anglais"]
    assert result.recall == 1.0


def test_a_real_title_wins_over_another_pages_alias():
    names = corpus_names([("Horn", []), ("Cor anglais", ["Horn"])])
    assert names["Horn"] == "Horn"


def test_unknown_sources_are_named_with_their_questions():
    questions = [question(["Oboe", "Oboes"], id="q1"), question(["Oboes"], id="q2")]
    with pytest.raises(UnknownSourceError) as error:
        check_sources(questions, NAMES)
    assert error.value.unknown == {"Oboes": ["q1", "q2"]}
    assert "'Oboes'" in str(error.value) and "q1, q2" in str(error.value)


def test_clarification_options_are_checked_too():
    q = GoldenQuestion(id="q9", question="?", category="c", difficulty="easy", expected_sources=[],
                       expected_behaviour="clarify", clarification_options=["Guitar", "Banjo"])
    with pytest.raises(UnknownSourceError) as error:
        check_sources([q], NAMES)
    assert error.value.unknown == {"Banjo": ["q9"]}


def test_known_sources_and_aliases_pass():
    check_sources([question(["English horn", "Guitar"])], NAMES)


def test_evaluate_skips_questions_that_are_not_answers_and_passes_filters():
    retriever = FakeRetriever([chunk("Oboe")] * 5)
    questions = [question(["Oboe"], id="q1"), question([], id="q2", behaviour="clarify")]
    filters = {"q1": Filters(source_type="encyclopedia")}
    results = evaluate(retriever, questions, NAMES, filters=filters)
    assert [r.id for r in results] == ["q1"]
    assert retriever.calls == [("?", 5, Filters(source_type="encyclopedia"))]


def test_summary_is_the_mean_per_question():
    results = [score(question(["Oboe"]), [chunk("Oboe")] * 5, NAMES),
               score(question(["Oboe"]), [chunk("Guitar")] * 5, NAMES)]
    summary = summarize(results)
    assert (summary.questions, summary.precision, summary.recall) == (2, 0.5, 0.5)
    assert summarize([]).questions == 0


def test_the_committed_golden_set_is_well_formed():
    path = Path(__file__).resolve().parents[2] / "data" / "golden-set.json"
    questions = load_golden_set(path)
    assert len(questions) >= 10
    assert len({q.id for q in questions}) == len(questions)
    for q in questions:
        assert q.question and q.category and q.difficulty and q.reference_answer
        if q.expected_behaviour == "answer":
            assert q.expected_sources, q.id
        else:
            assert not q.expected_sources, q.id
