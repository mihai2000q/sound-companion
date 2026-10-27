"""Run the injection test set. Run from the server folder:

    uv run python -m scripts.eval_injection [--cases PATH] [--repeats 3] [--model ID] [--only i06,i07] [--label L]

Request and tool cases need no model and run once. Agent cases (a direct override, a prompt leak, a planted
chunk, a mocked tool result, a delimiter escape) run on the chat model `--repeats` times and pass only when every run
passes, so a flaky defence shows as a failure. Searches are answered by planted chunks, never the Corpus. Prints
pass or fail per case, exits 1 on any failure. With `--label` the run is saved to
`eval/results/<date>-injection-<label>.json` (never overwritten) and two runs are compared with `scripts.compare_runs`.
"""

import argparse
import hashlib
import sys
from pathlib import Path

from app.agent.agent import make_chat_model
from app.agent.injection_eval import KIND, build_run, load_cases, run_case
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tool_eval import sha
from app.config import settings
from app.rag.eval_results import git_state, save_run

CASES = Path(__file__).resolve().parents[2] / "data" / "injection-tests.json"


def main(path: Path, repeats: int, model: str | None, only: set[str], label: str | None) -> int:
    cases = [c for c in load_cases(path) if not only or c.id in only]
    model_id = model or settings.openrouter_chat_model
    chat_model = make_chat_model(model_id) if any(c.kind == "agent" for c in cases) else None
    verdicts = [run_case(case, chat_model, repeats) for case in cases]

    print(f"{'id':4} {'result':6} {'runs':5} {'kind':8} type")
    for v in verdicts:
        print(f"{v.id:4} {'PASS' if v.passed else 'FAIL':6} {v.passes}/{v.runs:<3} {v.kind:8} {v.type}")
    for v in verdicts:
        for failure in v.failures:
            print(f"\n{v.id} {v.type}: {failure}")
    passed = sum(v.passed for v in verdicts)
    print(f"\n{passed}/{len(verdicts)} cases passed" + (f" (agent cases on {model_id}, {repeats} runs each)" if chat_model else ""))

    if label:
        run = build_run(
            f"{KIND}-{label}",
            {
                "model": model_id, "repeats": repeats, "prompt_sha256": sha(SYSTEM_PROMPT),
                "cases": {"file": path.name, "count": len(cases), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:12]},
                "git": git_state(),
            },
            verdicts,
        )
        print(f"saved {save_run(run).relative_to(Path.cwd())}")
    return 0 if passed == len(verdicts) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--repeats", type=int, default=3, help="runs per agent case, all must pass")
    parser.add_argument("--model", help="OpenRouter model id, default the configured chat model")
    parser.add_argument("--only", default="", help="comma-separated case ids")
    parser.add_argument("--label", help="save the run under this label")
    args = parser.parse_args()
    sys.exit(main(args.cases, args.repeats, args.model, {i for i in args.only.split(",") if i}, args.label))
