"""Run the behaviour checks of Story 5 against the real model and print what happened. Run from the server folder:

    uv run python -m scripts.check_behaviour [name ...]

Each case is a conversation on its own in-memory thread (no database writes), printed with its tool calls
and answers, so a person judges them. Automating the judgement is Story 9.
"""

import argparse
import asyncio

from langgraph.checkpoint.memory import InMemorySaver

from app.agent.agent import build_agent, make_chat_model
from app.rag.retriever import VectorRetriever

CASES = {  # name -> the user's turns
    "q15-guitar": ["Tell me about the guitar.", "electric"],
    "q16-saxophone": ["What is the range of a saxophone?"],
    "q17-transpose": ["Transpose it up a fifth."],
    "q02-specific": ["How does a clarinet produce sound, and what are its registers?"],
    "q05-alias": ["Is a cor anglais the same as an English horn, and what key is it in?"],
    "q13-acoustic": ["How does an acoustic guitar produce its sound?"],
    "q04-term": ["What is a Neapolitan sixth?"],
    "off-topic": ["Tell me a joke."],
    "off-topic-cooking": ["What is a good recipe for pancakes?"],
    "not-covered": ["How do I tune a theremin?", "What is the range of a sousaphone?"],
}


async def run_case(name: str, turns: list[str], retriever: VectorRetriever) -> None:
    print(f"\n{'=' * 70}\n{name}")
    agent = build_agent(make_chat_model(), retriever, InMemorySaver())
    config = {"configurable": {"thread_id": name}}
    seen = 0
    for turn in turns:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": turn}]}, config)
        print(f"\nyou> {turn}")
        for message in result["messages"][seen:]:
            for call in getattr(message, "tool_calls", None) or []:
                print(f"  [tool call] {call['args']}")
        seen = len(result["messages"])
        print(f"\n{result['messages'][-1].content}")


async def main(names: list[str]) -> None:
    retriever = VectorRetriever.from_settings()
    for name in names or CASES:
        await run_case(name, CASES[name], retriever)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", metavar="name", choices=list(CASES))
    asyncio.run(main(parser.parse_args().names))
