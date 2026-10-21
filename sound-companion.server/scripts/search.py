"""Similarity search over the indexed chunks. Run from the server folder:
`uv run python -m scripts.search "English horn" [-k 5]`.
"""

import argparse

from app.config import settings
from app.rag.embeddings import OpenRouterEmbeddings
from app.rag.vector_store import open_store


def main(query: str, k: int) -> None:
    embeddings = OpenRouterEmbeddings(
        settings.openrouter_api_key, settings.openrouter_base_url, settings.openrouter_embedding_model
    )
    store = open_store(embeddings)
    for document, distance in store.similarity_search_with_score(query, k=k):
        meta = document.metadata
        print(f"\n{1 - distance:.3f}  {meta['title']} > {meta['section'] or '(lead)'}")
        print("   " + document.page_content.split("\n", 1)[1][:200].replace("\n", " "))
    print(f"\ncost {embeddings.cost:.8f} credits")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()
    main(args.query, args.k)
