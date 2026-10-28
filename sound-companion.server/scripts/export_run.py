"""Run the golden set through the real agent and save the answers for RAGAs. Run from the server folder:

    uv run python -m scripts.export_run [--golden-set PATH] [--only q01,q02] [--mode vector|hybrid]

Each `answer` question is asked in its own thread on the chat model with the real retriever and the rewrite model
(clarify questions are skipped). Saves `data/runs/<timestamp>.json` with `question`, `answer`, `contexts` (retrieved
chunks), `tool_results` (music tool calls, kept apart) and `reference` per question. Every model call is written to
`usage_log`, and the run's cost is printed. Costs real credits: about a tenth of a credit for the whole set.
"""

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import build_agent, make_chat_model
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.run_export import answerable, build_export, export_run, save_export
from app.agent.tool_eval import sha
from app.config import RETRIEVER_MODES, settings
from app.db.usage import Ledger
from app.rag.eval_results import git_state
from app.rag.evaluation import load_golden_set
from app.rag.factory import make_retriever

DATA = Path(__file__).resolve().parents[2] / "data"


async def main(golden_set: Path, only: set[str], mode: str | None) -> int:
    questions, skipped = answerable(load_golden_set(golden_set))
    questions = [q for q in questions if not only or q.id in only]
    mode = mode or settings.retriever_mode
    agent = build_agent(
        make_chat_model(), make_retriever(mode), InMemorySaver(), make_chat_model(settings.openrouter_rewrite_model)
    )
    entries = await export_run(agent, questions, Ledger.from_settings())
    export = build_export(
        {
            "model": settings.openrouter_chat_model, "rewrite_model": settings.openrouter_rewrite_model,
            "retriever_mode": mode, "prompt_sha256": sha(SYSTEM_PROMPT), "git": git_state(),
            "golden_set": {"file": golden_set.name, "sha256": hashlib.sha256(golden_set.read_bytes()).hexdigest()[:12]},
        },
        entries, skipped,
    )
    for e in entries:
        print(f"{e.id:4} {len(e.contexts)} chunks {len(e.tool_results)} tool results {e.cost:.4f} credits"
              + (f"  ERROR {e.error}" if e.error else ""))
    print(f"\n{len(entries)} questions, skipped {', '.join(skipped) or 'none'}, {export['cost']:.4f} credits")
    print(f"saved {save_export(export, DATA / 'runs').relative_to(Path.cwd().parent)}")
    return 1 if any(e.error for e in entries) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--golden-set", type=Path, default=DATA / "golden-set.json")
    parser.add_argument("--only", default="", help="comma-separated question ids")
    parser.add_argument("--mode", choices=RETRIEVER_MODES, help="retriever, default RETRIEVER_MODE")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.golden_set, {i for i in args.only.split(",") if i}, args.mode)))
