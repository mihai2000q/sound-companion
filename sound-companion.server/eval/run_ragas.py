"""Score an exported run with RAGAs (docs/EVALUATION.md, layer 3). Run from the server folder:

    uv run --with ragas==0.4.3 python -m eval.run_ragas data/runs/<timestamp>.json [--only q01,q02] [--tool-contexts none|faithfulness|all] [--label L]

Prints faithfulness, answer relevancy, context precision and context recall per question and overall (the mean
of the questions that have a score), then the judge's spend. `OPENROUTER_JUDGE_MODEL` is the judge and
`OPENROUTER_EMBEDDING_MODEL` embeds for answer relevancy. The spend is written to `usage_log` (purpose `eval`).
A question whose answer used no retrieved chunk has no contexts, so it gets no faithfulness or context scores.
`--tool-contexts none|faithfulness|all` says which metrics also count the music tool results as contexts, default
`faithfulness` only (decision 72); `none` and `all` exist to compare. The scores are saved
to `eval/results/<date>-ragas-<label>.json` (never overwritten), the label defaulting to the export's name.
"""

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
NEEDS_CONTEXTS = {"faithfulness", "context_precision", "context_recall"}
KIND = "ragas"


@dataclass
class QuestionScores:
    id: str
    scores: dict[str, float | None]
    skipped: dict[str, str] = field(default_factory=dict)  # metric -> why it has no score


TOOL_MODES = ("none", "faithfulness", "all")  # which metrics count music tool results as contexts


def contexts_of(entry: dict, metric: str, tool_contexts: str = "faithfulness") -> list[str]:
    """The contexts a metric scores against: the retrieved chunks, and the music tool results after them when
    `tool_contexts` says this metric takes them (decision 72: faithfulness does, the retrieval metrics do not)."""
    contexts = list(entry["contexts"])
    if tool_contexts == "all" or (tool_contexts == "faithfulness" and metric == "faithfulness"):
        contexts += [f"{r['name']}({json.dumps(r['args'], ensure_ascii=False)}) returned {r['content']}" for r in entry["tool_results"]]
    return contexts


ATTEMPTS = 4  # a judge call that fails (a 429 that outlasted the client's retries) is tried again
BACKOFF_SECONDS = 10


async def score_entry(
    entry: dict, scorers: dict, tool_contexts: str = "faithfulness", sleep=asyncio.sleep
) -> QuestionScores:
    """Every metric of one entry. A metric that cannot be scored, or whose judge call keeps failing, is None with a reason."""
    result = QuestionScores(entry["id"], {m: None for m in scorers})
    if entry.get("error") or not entry["answer"].strip():
        result.skipped = {m: "the agent run failed" for m in scorers}
        return result

    async def score(metric: str) -> None:
        if metric in NEEDS_CONTEXTS and not contexts_of(entry, metric, tool_contexts):
            result.skipped[metric] = "no contexts"
            return
        for attempt in range(1, ATTEMPTS + 1):
            try:
                result.scores[metric] = float(await scorers[metric](entry))
                result.skipped.pop(metric, None)
                return
            except Exception as error:  # one failed judge call must not lose the rest of the run
                result.skipped[metric] = f"{type(error).__name__}: {error}"
                if attempt < ATTEMPTS:
                    await sleep(BACKOFF_SECONDS * attempt)

    for metric in scorers:  # one at a time: four at once trips the judge's rate limit
        await score(metric)
    return result


def summarize(results: list[QuestionScores]) -> dict[str, dict]:
    """Per metric: the mean over the questions that have a score, and how many that is."""
    summary = {}
    for metric in METRICS:
        values = [r.scores[metric] for r in results if r.scores.get(metric) is not None]
        summary[metric] = {"mean": sum(values) / len(values) if values else None, "questions": len(values)}
    return summary


def build_run(label: str, settings: dict, results: list[QuestionScores], spend: dict, when: date | None = None) -> dict:
    return {
        "kind": KIND,
        "label": f"ragas-{label}",
        "date": (when or date.today()).isoformat(),
        "settings": settings,
        "summary": summarize(results),
        "spend": spend,
        "questions": [{"id": r.id, "scores": r.scores, "skipped": r.skipped} for r in results],
    }


def fmt(value: float | None) -> str:
    return "  -  " if value is None else f"{value:5.2f}"


def print_table(results: list[QuestionScores], summary: dict) -> None:
    print(f"{'id':5} " + " ".join(f"{m:>17}" for m in METRICS))
    for r in results:
        print(f"{r.id:5} " + " ".join(f"{fmt(r.scores.get(m)):>17}" for m in METRICS))
    print(f"{'mean':5} " + " ".join(f"{fmt(summary[m]['mean']):>17}" for m in METRICS))
    print(f"{'n':5} " + " ".join(f"{summary[m]['questions']:>17}" for m in METRICS))
    for r in results:
        for metric, why in r.skipped.items():
            print(f"{r.id} {metric}: no score ({why})")


def contexts_of_metric(tool_contexts: str):
    return lambda entry, metric: contexts_of(entry, metric, tool_contexts)


async def run(export: dict, scorers: dict, only: set[str], tool_contexts: str) -> list[QuestionScores]:
    entries = [e for e in export["entries"] if not only or e["id"] in only]
    return [await score_entry(e, scorers, tool_contexts) for e in entries]


def main(path: Path, only: set[str], tool_contexts: str, label: str | None) -> int:
    from app.config import settings
    from app.db.usage import SqlUsageStore, Usage
    from app.rag.eval_results import git_state, save_run
    from eval.judge import Spend, make_scorers, metered_client

    export = json.loads(path.read_text(encoding="utf-8"))
    spend = Spend()
    scorers = make_scorers(
        metered_client(spend), settings.openrouter_judge_model, settings.openrouter_embedding_model,
        contexts_of_metric(tool_contexts),
    )
    results = asyncio.run(run(export, scorers, only, tool_contexts))
    summary = summarize(results)
    print_table(results, summary)

    thread_id, request_id = f"ragas-{path.stem}", uuid.uuid4()
    store = SqlUsageStore.from_settings()
    for model, (calls, prompt, completion, credits) in spend.models.items():
        store.add(thread_id, request_id, Usage("eval", model, int(prompt), int(completion), credits))
        print(f"\njudge {model}: {int(calls)} calls, {int(prompt)} prompt and {int(completion)} completion tokens, {credits:.4f} credits")
    print(f"total spend {spend.credits:.4f} credits (written to usage_log as eval)")

    run_record = build_run(
        label or path.stem,
        {
            "export": path.name, "export_settings": export.get("settings"), "judge_model": settings.openrouter_judge_model,
            "embedding_model": settings.openrouter_embedding_model, "tool_contexts": tool_contexts, "git": git_state(),
        },
        results,
        {"credits": spend.credits, "models": spend.models},
    )
    print(f"saved {save_run(run_record).relative_to(Path.cwd())}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("export", type=Path, help="a file written by scripts.export_run")
    parser.add_argument("--only", default="", help="comma-separated question ids")
    parser.add_argument(
        "--tool-contexts", choices=TOOL_MODES, default="faithfulness",
        help="which metrics count music tool results as contexts (default faithfulness only)",
    )
    parser.add_argument("--label", help="name of the saved scores, default the export's name")
    args = parser.parse_args()
    sys.exit(main(args.export, {i for i in args.only.split(",") if i}, args.tool_contexts, args.label))


def rounded(score: float | None) -> float | None:
    return None if score is None else round(score, 2)


def compare(a: dict, b: dict) -> dict:
    """Change from run `a` to run `b`: the mean of each metric, the questions whose score moved, the settings that differ."""
    in_b = {q["id"]: q for q in b["questions"]}
    changed = []
    for q in a["questions"]:
        other = in_b.get(q["id"])
        if other is None:
            continue
        # two decimals: answer relevancy generates and embeds questions, so it moves a little on every run
        pairs = {m: (rounded(q["scores"].get(m)), rounded(other["scores"].get(m))) for m in METRICS}
        moves = {m: pair for m, pair in pairs.items() if pair[0] != pair[1]}
        if moves:
            changed.append({"id": q["id"], "moves": moves})
    return {
        "summary": {m: (a["summary"][m], b["summary"][m]) for m in METRICS},
        "changed": changed,
        "only_in_a": [q["id"] for q in a["questions"] if q["id"] not in in_b],
        "only_in_b": sorted(in_b.keys() - {q["id"] for q in a["questions"]}),
    }
