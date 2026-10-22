"""Check that Convention-conflict answers name every Convention and cite its page (q06, q12). Run from the
server folder, with the Corpus indexed:

    uv run python -m scripts.check_conventions [id ...]

Runs the real agent and retriever on each question, prints the answer and what is missing, and exits 1 when a
case fails. A few thousand tokens per question on the chat model.
"""

import argparse
import asyncio
import sys

from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import build_agent, make_chat_model
from app.config import settings
from app.agent.convention_check import CASES, check_answer
from app.rag.retriever import VectorRetriever


async def main(ids: list[str]) -> int:
    agent = build_agent(
        make_chat_model(), VectorRetriever.from_settings(), InMemorySaver(), make_chat_model(settings.openrouter_rewrite_model)
    )
    failed = 0
    for case in (c for c in CASES if not ids or c.id in ids):
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": case.question}]}, {"configurable": {"thread_id": case.id}}
        )
        answer = result["messages"][-1].content
        check = check_answer(case, answer)
        failed += not check.ok
        print(f"\n{'=' * 70}\n{case.id}: {case.question}\n\n{answer}\n")
        print(f"-> {'ok' if check.ok else 'FAIL'}", end="")
        if not check.ok:
            print(
                f"  missing conventions: {check.missing_conventions or '-'}, missing citations: "
                f"{check.missing_citations or '-'}, says they differ: {check.says_they_differ}", end=""
            )
        print()
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="*", metavar="id", choices=[c.id for c in CASES])
    sys.exit(asyncio.run(main(parser.parse_args().ids)))
