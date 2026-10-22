"""Tool-calling accuracy on the tool golden file. Run from the server folder:

    uv run python -m scripts.eval_tools [--golden-tools PATH] [--model ID] [--real-retriever]
    uv run python -m scripts.eval_tools --label baseline

Runs the agent on each question and prints tool selection (the right set of tools called) and parameter
accuracy (every expected argument right) overall and per difficulty, then the failed cases. Searches
are answered by a stub, so no database is needed (`--real-retriever` uses the Corpus instead). With
`--label` the run is saved to `eval/results/<date>-tools-<label>.json` (never overwritten) and two runs
are compared with `scripts.compare_runs`. Costs a few thousand tokens per question on the chat model.
"""

import argparse
import hashlib
import sys
from pathlib import Path

import httpx

from app.agent.agent import build_agent, make_chat_model
from app.agent.tool_eval import StubRetriever, build_run, evaluate, load_cases, prompt_and_tools, summarize
from app.config import settings
from app.rag.eval_results import git_state, save_run

GOLDEN_TOOLS = Path(__file__).resolve().parents[2] / "data" / "golden-tools.json"


def fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def model_prices(model_id: str) -> tuple[float, float] | None:
    """(input, output) USD per million tokens from OpenRouter's public model list, None when unavailable."""
    try:
        models = httpx.get("https://openrouter.ai/api/v1/models", timeout=10).json()["data"]
        pricing = next(m["pricing"] for m in models if m["id"] == model_id)
        return float(pricing["prompt"]) * 1e6, float(pricing["completion"]) * 1e6
    except Exception:
        return None


def describe(calls: list[dict]) -> str:
    return ", ".join(f"{c['name']}({c['args']})" for c in calls) or "no tool"


def main(golden: Path, label: str | None, model: str | None, real_retriever: bool) -> int:
    cases = load_cases(golden)
    if real_retriever:
        from app.rag.retriever import VectorRetriever

        retriever = VectorRetriever.from_settings()
    else:
        retriever = StubRetriever()
    model_id = model or settings.openrouter_chat_model
    agent = build_agent(make_chat_model(model_id), retriever)
    results = evaluate(agent, cases)

    print(f"{'id':4} {'tools':5} {'args':5} {'difficulty':10} question")
    for r in results:
        args = "-" if r.parameters_ok is None else ("ok" if r.parameters_ok else "FAIL")
        print(f"{r.id:4} {'ok' if r.selection_ok else 'FAIL':5} {args:5} {r.difficulty:10} {r.question[:60]}")
    print(f"\n{'':10} {'cases':>5} {'selection':>10} {'parameters':>11}")
    for s in summarize(results):
        print(f"{s.group:10} {s.cases:5} {fmt(s.selection):>10} {fmt(s.parameter):>8} of {s.parameter_cases}")
    failed = [r for r in results if not r.selection_ok or r.parameters_ok is False]
    for r in failed:
        print(f"\n{r.id} {r.question}\n  expected: {describe(r.expected)}\n  actual:   {describe(r.actual)}"
              + (f"\n  error: {r.error}" if r.error else ""))
    errored = [r.id for r in results if r.error]
    if errored:
        print(f"\nWARNING: the agent run raised on {len(errored)} cases ({', '.join(errored)}), for example a provider "
              "rate limit. Those count as failures here, so the run is not saved: run again.")
    input_tokens, output_tokens = sum(r.input_tokens for r in results), sum(r.output_tokens for r in results)
    prices = model_prices(model_id)
    cost = None if prices is None else (input_tokens * prices[0] + output_tokens * prices[1]) / 1e6
    print(f"\n{input_tokens} input + {output_tokens} output tokens on {model_id}"
          + ("" if cost is None else f", about ${cost:.4f} at ${prices[0]:g} / ${prices[1]:g} per million"))

    if label and errored:
        return 1
    if label:
        run = build_run(
            f"tools-{label}",
            {
                "model": model_id,
                "price_per_million_usd": None if prices is None else {"input": prices[0], "output": prices[1]},
                "retriever": "real (VectorRetriever)" if real_retriever else "stub",
                **prompt_and_tools(retriever),
                "golden_tools": {
                    "file": golden.name, "cases": len(cases),
                    "sha256": hashlib.sha256(golden.read_bytes()).hexdigest()[:12],
                },
                "git": git_state(),
            },
            results,
        )
        print(f"saved {save_run(run).relative_to(Path.cwd())}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--golden-tools", type=Path, default=GOLDEN_TOOLS)
    parser.add_argument("--label", help="save the run under this label")
    parser.add_argument("--model", help="OpenRouter model id, default the configured chat model")
    parser.add_argument("--real-retriever", action="store_true", help="search the Corpus instead of the stub")
    args = parser.parse_args()
    sys.exit(main(args.golden_tools, args.label, args.model, args.real_retriever))
