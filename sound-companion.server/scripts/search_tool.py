"""Call the `search_knowledge_base` tool directly, the way the agent will. Run from the server folder:

    uv run python -m scripts.search_tool
    uv run python -m scripts.search_tool "what is a cadence" --topic form --source-type textbook

With no query it runs "English horn" and then a filtered query, to show the results differ.
"""

import argparse

from app.rag.retriever import VectorRetriever
from app.tools.search import make_search_tool


def call(tool, **args) -> None:
    args = {name: value for name, value in args.items() if value}
    print(f"\n=== {tool.name}({args})\n")
    print(tool.invoke(args))


def main(args: argparse.Namespace) -> None:
    retriever = VectorRetriever.from_settings()
    tool = make_search_tool(retriever, k=args.k)
    if args.query:
        call(tool, query=args.query, source_type=args.source_type, topic=args.topic, title=args.title)
    else:
        call(tool, query="English horn")
        call(tool, query="how are phrases built", source_type="textbook", topic="form")
        call(tool, query="English horn", source_type="blog")
    print(f"\ncost {retriever.embedding_cost:.8f} credits")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query", nargs="?")
    parser.add_argument("-k", type=int, default=3)
    parser.add_argument("--topic")
    parser.add_argument("--title")
    parser.add_argument("--source-type")
    main(parser.parse_args())
