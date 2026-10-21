"""Create the chunk table. Run from the server folder: `uv run python -m scripts.setup_chunks`.

Safe to run twice: an existing table is left as it is.
"""

from app.rag.vector_store import CHUNKS_TABLE, create_chunk_table

if __name__ == "__main__":
    created = create_chunk_table()
    print(f"Created table '{CHUNKS_TABLE}'." if created else f"Table '{CHUNKS_TABLE}' already exists.")
