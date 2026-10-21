"""One-off check of `hnsw.iterative_scan` on the real Corpus (Story 3, issue 20). Run from the server
folder: `uv run python -m scripts.check_iterative_scan`. Spends one embedding call.

At about 7,000 chunks the planner may prefer a sequential scan, so the check forces index scans with
`enable_seqscan=off` and compares selective filters with and without the option, through a pool of
one connection and under concurrent threads. It also reads `hnsw.iterative_scan` and the backend pid
on the query's own connection, to confirm `SET LOCAL` landed there.
"""

from concurrent.futures import ThreadPoolExecutor

from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import HNSWQueryOptions
from sqlalchemy import create_engine, event, text

from app.config import settings
from app.rag.chunking import METADATA_COLUMNS
from app.rag.embeddings import OpenRouterEmbeddings
from app.rag.filters import topic_filter
from app.rag.vector_store import CHUNKS_TABLE, HnswIterative

K = 10
FILTERS = {
    "title = Cor anglais (33 chunks)": {"title": "Cor anglais"},
    "topic transposition": topic_filter(["transposition"]),
    "topic post-tonal (textbook only)": topic_filter(["post-tonal"]),
    "topics percussion and electronic": topic_filter(["percussion", "electronic"], "all"),
}


def make_store(options, **engine_options) -> PGVectorStore:
    engine = PGEngine.from_connection_string(settings.database_url_async, **engine_options)
    store = PGVectorStore.create_sync(
        engine, OpenRouterEmbeddings("unused", "unused", "unused"), CHUNKS_TABLE,
        metadata_columns=METADATA_COLUMNS, index_query_options=options,
    )
    return store


def main() -> None:
    embeddings = OpenRouterEmbeddings(
        settings.openrouter_api_key, settings.openrouter_base_url, settings.openrouter_embedding_model
    )
    vector = embeddings.embed_query("English horn")
    force_index = {"connect_args": {"options": "-c enable_seqscan=off"}}

    sync_engine = create_engine(settings.database_url_async)
    with sync_engine.connect() as connection:
        total = connection.execute(text(f"SELECT count(*) FROM {CHUNKS_TABLE}")).scalar()
        literal = str([float(x) for x in vector])
        for label, where in [("no filter", ""), ("title filter", "WHERE title = 'Cor anglais'")]:
            plan = connection.execute(text(
                f"EXPLAIN SELECT 1 FROM {CHUNKS_TABLE} {where} ORDER BY embedding <=> '{literal}' LIMIT {K}"
            )).scalars().all()
            print(f"default planner, {label}: {plan[1].strip() if len(plan) > 1 else plan[0]}")
    print(f"{total} chunks\n")

    print(f"Rows returned (k={K}), index scan forced:")
    print(f"{'filter':40} {'ef_search only':>15} {'with iterative':>15}")
    plain = make_store(HNSWQueryOptions(ef_search=40), **force_index)
    iterative = make_store(HnswIterative(), **force_index)
    for label, flt in FILTERS.items():
        without = len(plain.similarity_search_by_vector(vector, k=K, filter=flt))
        with_option = len(iterative.similarity_search_by_vector(vector, k=K, filter=flt))
        print(f"{label:40} {without:>15} {with_option:>15}")

    # One connection in the pool, 16 concurrent searches: every query must get the setting.
    pooled = make_store(HnswIterative(), pool_size=1, max_overflow=0, **force_index)
    seen: list[tuple[str, int]] = []

    @event.listens_for(pooled._engine._pool.sync_engine, "before_cursor_execute")
    def record(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("SELECT") and "distance" in statement:
            cursor.execute("SHOW hnsw.iterative_scan")
            setting = cursor.fetchone()[0]
            cursor.execute("SELECT pg_backend_pid()")
            seen.append((setting, cursor.fetchone()[0]))

    flt = FILTERS["title = Cor anglais (33 chunks)"]
    with ThreadPoolExecutor(8) as pool:
        counts = list(pool.map(lambda _: len(pooled.similarity_search_by_vector(vector, k=K, filter=flt)), range(16)))
    print(f"\nPool of 1, 16 searches on 8 threads: rows {sorted(set(counts))}")
    print(f"setting seen on the query's connection: {sorted({s for s, _ in seen})}, "
          f"backend pids: {sorted({pid for _, pid in seen})}, queries recorded: {len(seen)}")


if __name__ == "__main__":
    main()
