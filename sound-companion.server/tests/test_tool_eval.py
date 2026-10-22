from datetime import date

import pytest
from langchain_core.messages import AIMessage

from app.agent.agent import build_agent
from app.agent.tool_eval import (
    CaseResult, ExpectedCall, StubRetriever, ToolCase, build_run, compare, evaluate, load_cases, score_case,
    summarize, value_matches,
)
from app.rag.eval_results import load_run, save_run
from app.tools.registry import build_tools
from tests.test_agent import FakeToolModel
from tests.test_search_tool import FakeRetriever


def case(*expected: ExpectedCall, id="c1", difficulty="easy") -> ToolCase:
    return ToolCase(id=id, question="?", category="c", difficulty=difficulty, expected_tools=list(expected))


def call(name: str, **args) -> dict:
    return {"name": name, "args": args}


CHORD = ExpectedCall("chord_info", {"notes": ["D", "F", "A", "C"]})


def test_the_right_tool_with_the_right_arguments_scores_fully():
    assert score_case(case(CHORD), [call("chord_info", notes=["D", "F", "A", "C"])]) == (True, 1, 1)


def test_the_wrong_tool_fails_selection_and_matches_no_argument():
    assert score_case(case(CHORD), [call("scale_info", tonic="D", scale="major")]) == (False, 1, 0)


def test_a_wrong_note_or_number_is_not_accepted():
    assert score_case(case(CHORD), [call("chord_info", notes=["D", "F", "A", "C#"])]) == (True, 1, 0)
    freq = case(ExpectedCall("note_frequency", {"frequency": 450}))
    assert score_case(freq, [call("note_frequency", frequency=440)]) == (True, 1, 0)
    assert score_case(freq, [call("note_frequency", frequency=450.0)]) == (True, 1, 1)


def test_notes_are_exact_but_names_ignore_case():
    assert not value_matches("note", "Bb3", "bb3")
    assert not value_matches("tonic", "Eb", "D#")
    assert value_matches("instrument", "B-flat clarinet", " b-flat Clarinet ")
    assert value_matches("scale", "dorian", "Dorian")


def test_any_of_accepts_each_listed_spelling_and_nothing_else():
    expected = {"any_of": ["major", "ionian"]}
    assert value_matches("scale", expected, "Ionian")
    assert not value_matches("scale", expected, "minor")


def test_only_the_expected_arguments_are_checked():
    expected = case(ExpectedCall("search_knowledge_base", {"source_type": "textbook"}))
    assert score_case(expected, [call("search_knowledge_base", query="x", source_type="textbook", topic="y")]) == (True, 1, 1)
    assert score_case(expected, [call("search_knowledge_base", query="x")]) == (True, 1, 0)


def test_a_no_tool_case_fails_when_any_tool_is_called():
    assert score_case(case(), []) == (True, 0, 0)
    assert score_case(case(), [call("search_knowledge_base", query="joke")])[0] is False


def test_repeated_calls_are_counted():
    two = case(ExpectedCall("search_knowledge_base"), ExpectedCall("search_knowledge_base"))
    assert score_case(two, [call("search_knowledge_base", query="a"), call("search_knowledge_base", query="b")])[0]
    assert not score_case(two, [call("search_knowledge_base", query="a")])[0]
    assert not score_case(two, [call("search_knowledge_base", query="a")] * 3)[0]


def test_order_is_ignored():
    both = case(ExpectedCall("chord_info", {"notes": ["C", "E", "G"]}), ExpectedCall("note_frequency", {"note": "A4"}))
    calls = [call("note_frequency", note="A4"), call("chord_info", notes=["C", "E", "G"])]
    assert score_case(both, calls) == (True, 2, 2)


def test_two_expected_calls_of_one_tool_each_take_their_own_actual_call():
    two = case(
        ExpectedCall("interval_between", {"note_a": "C4", "note_b": "E4"}),
        ExpectedCall("interval_between", {"note_a": "C4", "note_b": "G4"}),
    )
    calls = [call("interval_between", note_a="C4", note_b="G4"), call("interval_between", note_a="C4", note_b="E4")]
    assert score_case(two, calls) == (True, 4, 4)


def result(id: str, difficulty: str, selection: bool, expected: int, matched: int) -> CaseResult:
    return CaseResult(id=id, question="?", category="c", difficulty=difficulty, expected=[], actual=[],
                      selection_ok=selection, args_expected=expected, args_matched=matched)


def test_summary_is_overall_then_per_difficulty_and_skips_cases_without_arguments():
    results = [
        result("a", "easy", True, 1, 1),
        result("b", "easy", False, 1, 0),
        result("c", "hard", True, 0, 0),  # no-tool case: no arguments to check
        result("d", "medium", True, 2, 1),
    ]
    rows = {s.group: s for s in summarize(results)}
    assert list(rows) == ["overall", "easy", "medium", "hard"]
    assert (rows["overall"].cases, rows["overall"].selection) == (4, 0.75)
    assert (rows["overall"].parameter_cases, rows["overall"].parameter) == (3, pytest.approx(1 / 3))
    assert rows["easy"].parameter == 0.5
    assert rows["hard"].parameter is None and rows["hard"].selection == 1.0


def agent_with(replies):
    return build_agent(FakeToolModel(messages=iter(replies), seen=[], bound=[]), FakeRetriever())


def test_evaluate_runs_the_agent_and_scores_the_calls_it_made():
    ask_chord = AIMessage("", tool_calls=[{"name": "chord_info", "args": {"notes": ["D", "F", "A", "C"]}, "id": "1"}])
    agent = agent_with([ask_chord, AIMessage("Dm7 or F6/D."), AIMessage("A joke? Not my field.")])
    [chord, joke] = evaluate(agent, [case(CHORD, id="chord"), case(id="joke")])
    assert chord.selection_ok and chord.parameters_ok is True
    assert [c["name"] for c in chord.actual] == ["chord_info"]
    assert joke.selection_ok and joke.parameters_ok is None and joke.actual == []


def test_a_model_that_calls_a_tool_when_none_is_expected_fails_the_case():
    search = AIMessage("", tool_calls=[{"name": "search_knowledge_base", "args": {"query": "joke"}, "id": "1"}])
    [joke] = evaluate(agent_with([search, AIMessage("No.")]), [case(id="joke")])
    assert not joke.selection_ok


def test_a_failed_run_is_a_failed_case_not_a_crash():
    class Broken:
        def invoke(self, *_):
            raise RuntimeError("boom")

    [failed] = evaluate(Broken(), [case(CHORD)])
    assert not failed.selection_ok and failed.error == "RuntimeError: boom"


def test_the_stub_retriever_answers_without_a_database():
    [chunk] = StubRetriever().retrieve("cornet", 5)
    assert "cornet" in chunk.content


def test_the_golden_tools_file_is_valid():
    from scripts.eval_tools import GOLDEN_TOOLS

    cases = load_cases(GOLDEN_TOOLS)
    assert len(cases) >= 15
    assert len({c.id for c in cases}) == len(cases)
    assert any(not c.expected_tools for c in cases)
    assert {c.difficulty for c in cases} <= {"easy", "medium", "hard"}
    names = {tool.name for tool in build_tools(StubRetriever())}
    assert {e.name for c in cases for e in c.expected_tools} <= names


def run(label: str, results: list[CaseResult], settings: dict | None = None) -> dict:
    return build_run(label, settings or {"model": "m"}, results, when=date(2026, 10, 22))


def test_a_run_is_saved_loaded_and_compared(tmp_path):
    before = run("tools-before", [result("a", "easy", False, 1, 0), result("b", "easy", True, 1, 1)], {"model": "m", "tools": {"chord_info": "x"}})
    after = run("tools-after", [result("a", "easy", True, 1, 1), result("b", "easy", True, 1, 1)], {"model": "m", "tools": {"chord_info": "y"}})
    assert load_run(save_run(before, tmp_path)) == before
    change = compare(before, after)
    assert [r["id"] for r in change["changed"]] == ["a"]
    overall_a, overall_b = change["summary"][0]
    assert (overall_a["selection"], overall_b["selection"]) == (0.5, 1.0)
    assert change["settings"] == {"tools.chord_info": ("x", "y")}
