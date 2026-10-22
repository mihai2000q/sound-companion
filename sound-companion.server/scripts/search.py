"""Search the indexed chunks through the `Retriever`. Run from the server folder:

    uv run python -m scripts.search "English horn" [-k 5]
    uv run python -m scripts.search "what is a cadence" --topic form --topic chords-and-harmony --any
    uv run python -m scripts.search "phrases" --source-type textbook --title "The sentence"
    uv run python -m scripts.search --demo

`--topic` is repeatable (all of them, or any of them with `--any`), `--title` and `--source-type`
narrow further. `--demo` runs one query with and without filters, to show the results differ.
"""

import argparse

from app.rag.retriever import Filters, Retriever, VectorRetriever


def show(retriever: Retriever, query: str, k: int, filters: Filters | None) -> None:
    print(f"\n=== {query!r}, k={k}" + (f", {filters}" if filters else ", no filter"))
    chunks = retriever.retrieve(query, k, filters)
    for chunk in chunks:
        print(f"{chunk.score:.3f}  [{chunk.source_type}] {chunk.title} > {chunk.section or '(lead)'}")
        print("       " + chunk.content.split("\n", 1)[1][:150].replace("\n", " "))
    if not chunks:
        print("(no rows)")


def main(args: argparse.Namespace) -> None:
    retriever = VectorRetriever.from_settings()
    if args.demo:
        query = "how are phrases built"
        show(retriever, query, 4, None)
        show(retriever, query, 4, Filters(source_type="encyclopedia"))
        show(retriever, query, 4, Filters(topics=("form",)))
        show(retriever, query, 4, Filters(topics=("form", "rhythm-and-meter"), topic_match="any"))
        show(retriever, "English horn", 3, None)
        show(retriever, "English horn", 3, Filters(title="Cor anglais"))
    else:
        filters = Filters(
            source_type=args.source_type,
            topics=tuple(args.topic),
            topic_match="any" if args.any else "all",
            title=args.title,
        )
        show(retriever, args.query, args.k, filters)
    print(f"\ncost {retriever.embedding_cost:.8f} credits")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query", nargs="?")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--topic", action="append", default=[])
    parser.add_argument("--any", action="store_true", help="match any topic instead of all")
    parser.add_argument("--title")
    parser.add_argument("--source-type", choices=["encyclopedia", "textbook"])
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if not args.query and not args.demo:
        parser.error("give a query or --demo")
    main(args)
