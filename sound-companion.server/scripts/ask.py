"""Ask the agent one question from the command line. Run from the server folder:

    uv run python -m scripts.ask "How does a clarinet produce sound?"

Prints each tool call, the answer and the token cost. One question per run, no memory yet.
"""

import argparse

from app.agent.agent import build_agent, make_chat_model
from app.rag.retriever import VectorRetriever


def main(question: str) -> None:
    retriever = VectorRetriever.from_settings()
    agent = build_agent(make_chat_model(), retriever)
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    tokens = 0
    for message in result["messages"]:
        for call in getattr(message, "tool_calls", None) or []:
            print(f"[tool call] {call['name']}({call['args']})")
        tokens += (getattr(message, "usage_metadata", None) or {}).get("total_tokens", 0)
    print("\n" + result["messages"][-1].content)
    print(f"\n[{tokens} tokens, {retriever.embedding_cost:.8f} embedding credits]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("question")
    main(parser.parse_args().question)
