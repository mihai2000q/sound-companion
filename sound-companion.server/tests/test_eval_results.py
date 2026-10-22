from datetime import date

import pytest

from app.rag.eval_results import build_run, compare, differing_settings, load_run, run_path, save_run
from app.rag.evaluation import GoldenQuestion, QuestionResult, Summary, derive_filters
from app.rag.retriever import Filters

NAMES = {"Oboe": "Oboe", "Clarinet": "Clarinet", "Guitar": "Guitar", "Acoustic guitar": "Guitar"}
TOPICS = {
    "Oboe": ["instruments", "woodwinds"],
    "Clarinet": ["instruments", "woodwinds", "transposition"],
    "Guitar": ["instruments", "strings"],
}


def question(id: str, sources: list[str], behaviour: str = "answer") -> GoldenQuestion:
    return GoldenQuestion(id=id, question="?", category="c", difficulty="easy",
                          expected_sources=sources, expected_behaviour=behaviour)


def result(id: str, precision: float, recall: float) -> QuestionResult:
    return QuestionResult(id=id, question="?", precision=precision, recall=recall,
                          expected_pages=["Oboe"], found_pages=[], retrieved=["Oboe > (lead)"])


def run(label: str, results: list[QuestionResult], settings: dict | None = None) -> dict:
    precision = sum(r.precision for r in results) / len(results)
    recall = sum(r.recall for r in results) / len(results)
    return build_run(label, settings or {"k": 5}, Summary(5, len(results), precision, recall), results, {},
                     when=date(2026, 10, 22))


def test_no_filters_means_no_filter_per_question():
    assert derive_filters([question("q1", ["Oboe"])], NAMES, TOPICS, "none") == {}


def test_the_oracle_filter_is_any_of_the_expected_pages_topics():
    filters = derive_filters([question("q1", ["Oboe", "Guitar"])], NAMES, TOPICS, "topics-oracle")
    assert filters["q1"] == Filters(topics=("instruments", "strings", "woodwinds"), topic_match="any")


def test_an_alias_as_expected_source_uses_its_pages_topics():
    filters = derive_filters([question("q1", ["Acoustic guitar"])], NAMES, TOPICS, "topics-oracle")
    assert filters["q1"].topics == ("instruments", "strings")


def test_the_mismatch_filter_is_a_topic_none_of_the_expected_pages_has():
    filters = derive_filters([question("q1", ["Oboe"])], NAMES, TOPICS, "topics-mismatch")
    topic = filters["q1"].topics[0]
    assert len(filters["q1"].topics) == 1
    assert topic not in TOPICS["Oboe"]
    assert topic in {t for topics in TOPICS.values() for t in topics}


def test_questions_that_are_not_answers_get_no_filter():
    questions = [question("q1", ["Oboe"]), question("q2", [], behaviour="clarify")]
    assert set(derive_filters(questions, NAMES, TOPICS, "topics-oracle")) == {"q1"}


def test_a_run_is_saved_and_loaded_unchanged(tmp_path):
    saved = run("baseline", [result("q1", 0.8, 0.5)])
    path = save_run(saved, tmp_path)
    assert path.name == "2026-10-22-baseline.json" == run_path(saved, tmp_path).name
    loaded = load_run(path)
    assert loaded == saved
    assert loaded["label"] == "baseline" and loaded["date"] == "2026-10-22"
    assert loaded["settings"] == {"k": 5}
    assert loaded["summary"]["precision"] == 0.8
    assert loaded["questions"][0]["id"] == "q1" and loaded["questions"][0]["retrieved"]


def test_a_saved_run_is_never_overwritten(tmp_path):
    saved = run("baseline", [result("q1", 0.8, 0.5)])
    save_run(saved, tmp_path)
    with pytest.raises(FileExistsError):
        save_run(saved, tmp_path)


def test_compare_gives_the_change_per_question_and_overall():
    a = run("a", [result("q1", 0.4, 0.5), result("q2", 1.0, 1.0)])
    b = run("b", [result("q1", 0.8, 1.0), result("q2", 1.0, 1.0), result("q3", 0.2, 0.0)])
    change = compare(a, b)
    first = change["questions"][0]
    assert first["id"] == "q1"
    assert first["precision_change"] == pytest.approx(0.4)
    assert first["recall_change"] == pytest.approx(0.5)
    assert change["only_in_b"] == ["q3"] and change["only_in_a"] == []
    assert change["precision_change"] == pytest.approx(b["summary"]["precision"] - a["summary"]["precision"])


def test_compare_names_the_settings_that_differ():
    a = {"settings": {"k": 5, "chunking": {"chunk_chars": 800, "overlap_chars": 100}, "filters": "none"}}
    b = {"settings": {"k": 5, "chunking": {"chunk_chars": 500, "overlap_chars": 100}, "filters": "none"}}
    assert differing_settings(a, b) == {"chunking.chunk_chars": (800, 500)}
    assert differing_settings(a, a) == {}
