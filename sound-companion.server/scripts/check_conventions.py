"""Check that Convention-conflict answers name every Convention and cite its page (q06, q12). Run from the
server folder, with the Corpus indexed:

    uv run python -m scripts.check_conventions [id ...] [--runs 3] [--mode vector|hybrid] [--model ID] [--verbose]

Runs the real agent and retriever on each question `--runs` times, prints what is missing, and exits 1 when
any run fails. `--verbose` prints every answer and the searches made. A few thousand tokens per run on the chat
model.
"""

import argparse
import asyncio
import sys

from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import build_agent, make_chat_model
from app.agent.convention_check import CASES, check_answer
from app.agent.tool_eval import tool_calls_of
from app.config import RETRIEVER_MODES, settings
from app.rag.factory import make_retriever


async def main(ids: list[str], runs: int, mode: str | None, model: str | None, verbose: bool) -> int:
    agent = build_agent(
        make_chat_model(model), make_retriever(mode), InMemorySaver(), make_chat_model(settings.openrouter_rewrite_model)
    )
    failed = 0
    for case in (c for c in CASES if not ids or c.id in ids):
        passed = 0
        for run in range(runs):
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": case.question}]}, {"configurable": {"thread_id": f"{case.id}-{run}"}}
            )
            answer = result["messages"][-1].content
            check = check_answer(case, answer)
            passed += check.ok
            calls = [f"{c['name']}({c['args']})" for c in tool_calls_of(result["messages"])]
            if verbose:
                print(f"\n{'=' * 70}\n{case.id} run {run + 1}: {case.question}\n\n{answer}\n\ncalls: {calls}")
            print(f"{case.id} run {run + 1}: {'ok' if check.ok else 'FAIL'}"
                  + ("" if check.ok else f"  missing conventions: {check.missing_conventions or '-'}, missing citations: "
                     f"{check.missing_citations or '-'}, says they differ: {check.says_they_differ}"))
        failed += passed < runs
        print(f"{case.id}: {passed}/{runs} runs pass")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="*", metavar="id", choices=[c.id for c in CASES])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--mode", choices=RETRIEVER_MODES, help="retriever, default RETRIEVER_MODE")
    parser.add_argument("--model", help="OpenRouter id of the chat model, default the configured one")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.ids, args.runs, args.mode, args.model, args.verbose)))
