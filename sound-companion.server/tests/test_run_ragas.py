import asyncio
from datetime import date

import httpx

from eval.judge import Spend, import_ragas, metered_client
from eval.run_ragas import METRICS, build_run, compare, contexts_of, score_entry, summarize


def entry(id="q01", contexts=("chunk",), tool_results=(), answer="An answer.", error=None) -> dict:
    return {
        "id": id, "question": "Q?", "answer": answer, "contexts": list(contexts), "tool_results": list(tool_results),
        "reference": "R.", "error": error,
    }


def fake_scorers(**overrides):
    async def fixed(e):
        return 0.5

    return {m: overrides.get(m, fixed) for m in METRICS}


def test_all_four_metrics_are_scored_for_an_entry_with_contexts():
    result = asyncio.run(score_entry(entry(), fake_scorers()))
    assert result.scores == {m: 0.5 for m in METRICS} and result.skipped == {}


def test_an_entry_without_contexts_keeps_only_answer_relevancy():
    result = asyncio.run(score_entry(entry(contexts=()), fake_scorers()))
    assert result.scores["answer_relevancy"] == 0.5
    assert [m for m, v in result.scores.items() if v is None] == ["faithfulness", "context_precision", "context_recall"]
    assert set(result.skipped.values()) == {"no contexts"}


def test_tool_results_count_as_contexts_only_for_the_metrics_that_take_them():
    tools = [{"name": "note_frequency", "args": {"note": "A4"}, "content": '{"hz": 440}'}]
    both = entry(contexts=("chunk",), tool_results=tools)
    tool_text = 'note_frequency({"note": "A4"}) returned {"hz": 440}'
    assert contexts_of(both, "faithfulness", "none") == ["chunk"]
    assert contexts_of(both, "faithfulness") == ["chunk", tool_text]  # the default
    assert contexts_of(both, "context_recall") == ["chunk"]
    assert contexts_of(both, "context_recall", "all") == ["chunk", tool_text]


def test_a_tool_only_answer_is_scored_for_faithfulness_but_not_for_retrieval():
    tools = [{"name": "scale_info", "args": {"tonic": "C"}, "content": "{}"}]
    result = asyncio.run(score_entry(entry(contexts=(), tool_results=tools), fake_scorers()))
    assert result.scores["faithfulness"] == 0.5 and result.scores["context_recall"] is None
    assert result.skipped == {"context_precision": "no contexts", "context_recall": "no contexts"}


def test_two_runs_are_compared_per_metric_and_question():
    one = asyncio.run(score_entry(entry("q01"), fake_scorers()))
    two = asyncio.run(score_entry(entry("q01"), fake_scorers(faithfulness=lambda e: _value(1.0))))
    a, b = (build_run(x, {}, [r], {}, date(2026, 10, 28)) for x, r in (("a", one), ("b", two)))
    result = compare(a, b)
    assert result["summary"]["faithfulness"][0]["mean"] == 0.5 and result["summary"]["faithfulness"][1]["mean"] == 1.0
    assert result["changed"] == [{"id": "q01", "moves": {"faithfulness": (0.5, 1.0)}}]


async def _value(x):
    return x


def test_a_judge_call_that_fails_once_is_tried_again():
    calls = []

    async def flaky(e):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("429")
        return 0.9

    async def no_sleep(seconds):
        pass

    result = asyncio.run(score_entry(entry(), fake_scorers(faithfulness=flaky), sleep=no_sleep))
    assert result.scores["faithfulness"] == 0.9 and result.skipped == {} and len(calls) == 2


def test_a_failed_judge_call_loses_one_score_not_the_run():
    async def broken(e):
        raise RuntimeError("judge down")

    async def no_sleep(seconds):
        pass

    result = asyncio.run(score_entry(entry(), fake_scorers(faithfulness=broken), sleep=no_sleep))
    assert result.scores["faithfulness"] is None and result.scores["context_recall"] == 0.5
    assert "judge down" in result.skipped["faithfulness"]


def test_a_failed_agent_run_is_not_scored():
    result = asyncio.run(score_entry(entry(error="boom"), fake_scorers()))
    assert all(v is None for v in result.scores.values())


def test_the_mean_ignores_questions_without_a_score():
    full = asyncio.run(score_entry(entry("q01"), fake_scorers()))
    bare = asyncio.run(score_entry(entry("q02", contexts=()), fake_scorers()))
    summary = summarize([full, bare])
    assert summary["faithfulness"] == {"mean": 0.5, "questions": 1}
    assert summary["answer_relevancy"] == {"mean": 0.5, "questions": 2}
    run = build_run("x", {}, [full, bare], {"credits": 0.01}, date(2026, 10, 28))
    assert run["label"] == "ragas-x" and run["kind"] == "ragas" and [q["id"] for q in run["questions"]] == ["q01", "q02"]


def test_the_meter_adds_up_the_usage_of_every_response():
    def reply(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "1", "object": "chat.completion", "created": 0, "model": "m/judge",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "hi"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": 0.002},
            },
        )

    async def calls() -> Spend:
        spend = Spend()
        client = metered_client(spend, httpx.MockTransport(reply))
        for _ in range(2):
            await client.chat.completions.create(model="m/judge", messages=[{"role": "user", "content": "hi"}])
        return spend

    spend = asyncio.run(calls())
    assert spend.models == {"m/judge": [2, 20, 10, 0.004]} and spend.credits == 0.004


def test_ragas_imports_with_the_vertexai_stand_in():
    import importlib.util

    import pytest

    if importlib.util.find_spec("ragas") is None:  # the optional group is not installed
        pytest.skip("ragas is not installed")
    _, _, metrics = import_ragas()
    assert all(hasattr(metrics, name) for name in ("Faithfulness", "AnswerRelevancy", "ContextPrecision", "ContextRecall"))
