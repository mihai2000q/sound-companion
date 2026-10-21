"""Similarity search over the indexed chunks. Run from the server folder:

    uv run python -m scripts.search "English horn" [-k 5]
    uv run python -m scripts.search "what is a cadence" --topic form --topic chords-and-harmony --any
    uv run python -m scripts.search --demo

`--topic` is repeatable (all of them, or any of them with `--any`), `--title` and `--source-type`
narrow further. `--demo` runs a sample query, an "English horn" query and a topic filter.
"""

import argparse

from app.config import settings
from app.rag.embeddings import OpenRouterEmbeddings
from app.rag.filters import combine, topic_filter
from app.rag.vector_store import open_store


def show(store, query: str, k: int, filter: dict | None) -> None:
    print(f"\n=== {query!r}, k={k}" + (f", filter {filter}" if filter else ""))
    results = store.similarity_search_with_score(query, k=k, filter=filter)
    for document, distance in results:
        meta = document.metadata
        print(f"{1 - distance:.3f}  [{meta['source_type']}] {meta['title']} > {meta['section'] or '(lead)'}")
        print("       " + document.page_content.split("\n", 1)[1][:150].replace("\n", " "))
    if not results:
        print("(no rows)")


def main(args: argparse.Namespace) -> None:
    embeddings = OpenRouterEmbeddings(
        settings.openrouter_api_key, settings.openrouter_base_url, settings.openrouter_embedding_model
    )
    store = open_store(embeddings)
    if args.demo:
        show(store, "How do I write music for a transposing instrument?", 3, None)
        show(store, "English horn", 3, None)
        show(store, "how are phrases built", 3, topic_filter(["form"]))
        show(store, "dissonance", 3, topic_filter(["acoustics", "notes-and-intervals"], "any"))
    else:
        flt = combine(
            topic_filter(args.topic, "any" if args.any else "all") if args.topic else None,
            {"title": args.title} if args.title else None,
            {"source_type": args.source_type} if args.source_type else None,
        )
        show(store, args.query, args.k, flt)
    print(f"\ncost {embeddings.cost:.8f} credits")


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
