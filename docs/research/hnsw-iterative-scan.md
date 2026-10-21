# HNSW and the iterative-scan setting on the real Corpus

Date: 2026-10-21. Issue 20 (Story 3, "Verify first"). Script: `sound-companion.server/scripts/check_iterative_scan.py`. Table `chunks` with 7,329 real chunks (1536 dimensions), HNSW index `chunkslangchainvectorindex` (`m=16`, `ef_construction=64`, cosine), pgvector in `pgvector/pgvector:pg16`, `langchain-postgres==0.0.19`. One embedding call (about 0.0000004 credits).

## Does Postgres use the index?

No, not at this size. `EXPLAIN` of the dense query with the default planner shows a sequential scan plus sort, with and without a filter (cost about 1,116 unfiltered and 958 with a 33-row title filter). The index only comes into play when the table is larger, so the check forces it with `enable_seqscan=off` (passed through `connect_args`).

## Rows returned with an index scan (k=10)

| Filter | `ef_search=40` only | with `HnswIterative` (`iterative_scan = relaxed_order`, `ef_search = 100`, `max_scan_tuples = 20000`) |
|---|---|---|
| `title = 'Cor anglais'` (33 chunks) | 7 | 10 |
| topic `transposition` | 10 | 10 |
| topic `post-tonal` (textbook pages only) | 0 | 10 |
| topics `percussion` and `electronic` (all of) | 0 | 0 (correct, no chunk has both, checked in SQL) |

So the spike's finding holds on real data: a selective filter against the HNSW index silently returns too few rows, or none, without the iterative scan.

## Does the setting reach the query through the pool?

Yes. The library runs `SET LOCAL` and the dense query on the same `conn` inside one transaction (`AsyncPGVectorStore.__query_collection`). The check used a pool of one connection (`pool_size=1`, `max_overflow=0`) and 16 searches on 8 threads. A `before_cursor_execute` hook read `SHOW hnsw.iterative_scan` and `pg_backend_pid()` on the cursor that was about to run each dense query:

- all 16 queries saw `relaxed_order`,
- all 16 ran on the same backend (one pid), so the single connection was shared and the setting held every time,
- every search returned 10 rows.

Not tested: a pool behind PgBouncer in transaction mode (not planned), and tables large enough for the planner to choose the index by itself.

## Other facts

- `store.is_valid_index()` returns False when the index does not exist, so index creation can be made idempotent (`ensure_vector_index`).
- `$like '%|form|%'` on the pipe-delimited `topics` column matches textbook pages too: 36 textbook and 7 encyclopedia documents carry `form`. A bare `%form%` would also match longer topics, the pipes prevent it.
- Search on "English horn" puts Cor anglais first (0.644), then French horn chunks (0.64). Dense search alone is not precise on names, which is what hybrid search (Story 15) is for.
