"""Create the chunk table, its HNSW index and the keyword column with its GIN index. Run from the server folder:
`uv run python -m scripts.setup_chunks`.

Safe to run twice: an existing table and index are left as they are.
"""

from app.config import settings
from app.rag.embeddings import OpenRouterEmbeddings
from app.rag.vector_store import CHUNKS_TABLE, create_chunk_table, ensure_keyword_index, ensure_vector_index, open_store

if __name__ == "__main__":
    created = create_chunk_table()
    print(f"Created table '{CHUNKS_TABLE}'." if created else f"Table '{CHUNKS_TABLE}' already exists.")
    embeddings = OpenRouterEmbeddings(
        settings.openrouter_api_key, settings.openrouter_base_url, settings.openrouter_embedding_model
    )  # no embedding call is made here
    indexed = ensure_vector_index(open_store(embeddings))
    print("Created the HNSW index." if indexed else "The HNSW index already exists.")
    ensure_keyword_index()
    print("The keyword column and its GIN index are in place.")
