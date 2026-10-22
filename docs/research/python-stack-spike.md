# Python backend stack spike (langchain-postgres, music libraries, LangChain v1 agent, FastAPI SSE)

Date: 2026-10-19. Python 3.12.3 (macOS, venv), throwaway `pgvector/pgvector:pg16` container (pgvector 0.8.7) on port 54330, removed at the end (`docker rm -f pgvspike-py`, confirmed gone). Fake deterministic 1536-dim embeddings (token-hash bag, L2-normalised) and a hand-written fake tool-calling chat model. No API key was read or used, no network LLM call was made. Scripts are in the session scratchpad `.../scratchpad/spike/` (`common.py`, `fakes.py`, `a1.py` to `a6.py`, `c1.py`, `c2.py`, `app.py`) and `.../scratchpad/libs/` (`t_m21.py`, `t_m21b.py`, `t_pychord.py`, `t_pyth.py`). No file in the project was modified except this new report.

## Verdict

| # | Item | Verdict | Note |
|---|------|---------|------|
| A1 | Install, versions | PASS | `langchain-postgres 0.0.19`, `langchain-core 1.6.12`, `psycopg 3.3.6`, SQLAlchemy 2.1.5. Works with psycopg3 as the async driver (`postgresql+psycopg://`). |
| A2 | Table via library helper (`init_vectorstore_table`) | PASS | Real columns for our metadata via `metadata_columns`, plus a leftover JSON column. No index created. |
| A3a | Re-add same ids | PASS | Upsert (`ON CONFLICT (id) DO UPDATE`), including metadata. Better than the JS store. |
| A3b | Delete by ids / by filter | PASS | Both work. `filter={}` and no arguments delete nothing (return False). Safer than the JS store. |
| A4 | Filters | PARTLY | Equality, `$in`, `$nin`, `$ne`, `$gt/$gte/$lt/$lte`, `$between`, `$exists`, `$like`, `$and`, `$or`, `$not` all correct. No array-contains on a `text[]` column. Workaround found (pipe-delimited text + `$like`). Unknown operators raise instead of being silently ignored. |
| A5 | similarity_search, score, retriever, MMR | PASS | Score is cosine DISTANCE (lower is better). Retriever `k`/`filter` and MMR work. |
| A6 | HNSW index, filter interaction, iterative scan | PARTLY | `apply_vector_index(HNSWIndex(...))` works at 1536 dims. The built-in `HNSWQueryOptions` only sets `ef_search`. `hnsw.iterative_scan` is not built in, but a 6-line custom `QueryOptions` subclass works and fixed the "too few rows" problem. |
| A7 | Hybrid search (HybridSearchConfig, RRF) | PARTLY | Keyword-only "Neapolitan" found with a useless vector, filters work with hybrid, alias title line works. But the shared config object is mutated on the first query (stale keyword query on all later queries) unless a fresh config is passed per call. RRF is rank-only, so useless-vector noise competes with keyword hits. |
| A7b | Scale: 3,000 chunks of about 800 chars | PARTLY | Insert is slow: 7 to 11 s (one INSERT and commit per row). Hybrid query median 27 ms, filtered hybrid 12 to 14 ms. |
| A8 | Surprises or blockers | PARTLY | None blocking. See section A8. |
| B | Music library | PARTLY | No single Python library matches `tonal`. `pychord` (MIT) covers chord detection and transposition exactly like `tonal`. `music21` (BSD) covers everything else but is heavy. Recommended: `pychord` plus a small hand-written module, `music21` optional. |
| C1 | `create_agent` + Postgres checkpointer | PASS | Sync `PostgresSaver` and `AsyncPostgresSaver` both work. Memory across turns confirmed. |
| C2 | Streaming (messages, updates, custom) | PASS | Tokens, tool calls, tool results, custom events all map cleanly to typed SSE events. |
| C3 | FastAPI SSE with `curl -N` | PASS | Works. CORS configured and verified. Proxy buffering through Vite/nginx not tested. |
| C4 | OpenRouter `usage.cost` on streamed responses | PARTLY | Live run on 2026-10-21: five checks pass, `usage.cost` is DROPPED on streamed responses by `langchain-openai`. A small `ChatOpenAI` subclass restores it (decision 46). See C4. |

## Part A: langchain-postgres `PGVectorStore` (v2 API)

### A1. Versions

```
Python 3.12.3
langchain-postgres 0.0.19 (latest on PyPI today)   langchain-core 1.6.12   langchain 1.4.6
langgraph 1.2.16   langgraph-checkpoint-postgres 3.2.0   langgraph-checkpoint 4.3.0
psycopg 3.3.6 (+ psycopg-binary, psycopg-pool 3.3.3)   SQLAlchemy 2.1.5   asyncpg 0.32.0   pgvector 0.3.6
fastapi 0.149.0   uvicorn 0.54.0
```

Install: `pip install langchain-postgres langchain-core "psycopg[binary]" langchain langgraph langgraph-checkpoint-postgres fastapi uvicorn`. No dependency conflicts. `PGEngine`, `PGVectorStore`, `Column` are exported from `langchain_postgres`. `HybridSearchConfig`, `reciprocal_rank_fusion`, `HNSWIndex`, `HNSWQueryOptions` are NOT exported at top level. Import them from `langchain_postgres.v2.hybrid_search_config` and `langchain_postgres.v2.indexes`.

### A2. Table creation and DDL

```python
engine = PGEngine.from_connection_string("postgresql+psycopg://postgres:spike@localhost:54330/postgres")
engine.init_vectorstore_table("chunks_cols", 1536, overwrite_existing=True, metadata_columns=[
  Column("document_id","TEXT"), Column("title","TEXT"), Column("aliases","TEXT[]"),
  Column("source_type","TEXT"), Column("topics","TEXT[]"), Column("section","TEXT"),
  Column("url","TEXT"), Column("license","TEXT"), Column("revision_id","INTEGER")])
vs = PGVectorStore.create_sync(engine, emb, "chunks_cols", metadata_columns=[...same names...])
```

Generated DDL (`\d`):

```
 langchain_id       | uuid         | not null            (PRIMARY KEY, no default)
 content            | text         | not null
 embedding          | vector(1536) | not null
 document_id text, title text, aliases text[], source_type text, topics text[], section text,
 url text, license text, revision_id integer          (all nullable by default)
 langchain_metadata | json                              (leftover for metadata keys not in metadata_columns)
Indexes: chunks_cols_pkey PRIMARY KEY, btree (langchain_id)
```

Without `metadata_columns` all metadata goes into the `langchain_metadata JSON` column (`json`, not `jsonb`). The helper also runs `CREATE EXTENSION IF NOT EXISTS vector`. No vector index is created.

Real columns versus JSON, both measured:
- Real columns: typed comparisons (`integer`, `text`), validated, can be indexed with plain btree, round trip returns the original types (lists come back as lists, `revision_id` as int). The column list must be repeated in `create_sync(..., metadata_columns=[...])`. Metadata keys that are not declared are silently kept in the JSON column.
- JSON only: filters on JSON keys also work (`{"source_type":"wiki"}`, `{"revision_id":{"$gt":102}}`, `$in`, `$or` all returned correct results). Comparison operators cast based on the Python type of the filter value. The docstring says filters do not work on JSON keys, which is wrong for 0.0.19. Delete by JSON-key filter also worked.
- Neither gives array-contains (see A4). Real columns are the better choice for `document_id`, `source_type`, `revision_id`. Our DATABASE-SCHEMA.md says `document_id` lives inside `metadata` because the JS store has no real columns. With this library we can make `document_id` a real column, so deleting a document is `delete(filter={"document_id": "14"})`.
- Our planned layout (`id`, `content`, `metadata jsonb`, `embedding`) is not what this library creates. Column names are configurable (`id_column`, `content_column`, `embedding_column`, `metadata_json_column`) but the metadata JSON column is type `json` created by the helper. The library can attach to a table we create ourselves if it has a vector column, a text content column and an id column, but table creation by the helper is the supported route.

### A3. add_documents, idempotency, delete

```python
ids = [str(uuid.uuid4()) for _ in docs]
vs.add_documents(docs, ids=ids)                       # True: returns the ids
vs.add_documents(edited_docs, ids=ids)                # same ids again
```

Result: no error. Second call is an upsert. Count stayed 5, content changed to the edited text. The SQL ends with `ON CONFLICT ("langchain_id") DO UPDATE SET content=EXCLUDED.content, embedding=..., <tsv column>=..., <json column>=..., <each metadata column>=...`. Same on the JSON-only table. This is a clear advantage over the JS store (plain INSERT, throws on duplicates). Ids must be valid UUID strings with the default id column type; a custom `Column("id","TEXT")` for `id_column` is possible at table creation.

Delete (with the 5-row test table):

| Call | Result |
|---|---|
| `vs.delete(ids=[one id])` | True, 4 left |
| `vs.delete(filter={"source_type":"wiki"})` | True, 2 left |
| `vs.delete(filter={})` | False, nothing deleted (count stayed 2) |
| `vs.delete()` | False, nothing deleted |
| `vs.delete(filter={"$or":[{"source_type":"textbook"},{"document_id":"16"}]})` | True, 0 left |
| `vs.delete(filter={"source_type":{"$foo":1}})` | `ValueError: Invalid operator: $foo. Expected one of {...}` |
| JSON-only table, `delete(filter={"source_type":"wiki"})` | True, 3 left |

The empty-filter case is safe (the code checks `if not ids and not filter: return False`). Unlike the JS store, an empty filter does not delete everything.

### A4. Filters (`a2.py`, 5 docs, query "double reed woodwind instrument")

| Filter | Result |
|---|---|
| `{"source_type":"wiki"}` | PASS (Oboe, Tuba) |
| `{"document_id":"12"}` | PASS |
| `{"document_id":12}` (int against text column) | ERROR `operator does not exist: text = smallint`. No coercion, use the right type. |
| `{"source_type":{"$in":["wiki","textbook"]}}` | PASS |
| `{"source_type":{"$nin":["encyclopedia"]}}` | PASS |
| `{"source_type":{"$ne":"encyclopedia"}}` | PASS |
| `{"source_type":{"$in":[]}}` | PASS, returns `[]` (no SQL error, unlike JS) |
| `{"revision_id":{"$gte":104}}` (integer column) | PASS (Cello, Sonata form) |
| `{"revision_id":{"$between":[102,104]}}` | PASS |
| `{"license":{"$exists":True}}` | PASS |
| `{"license":None}` | `[]` (equality with NULL never true; use `$exists: False`) |
| `{"$and":[{"source_type":"encyclopedia"},{"document_id":{"$in":["12","16"]}}]}` | PASS |
| `{"$or":[{"source_type":"wiki"},{"source_type":"textbook"}]}` | PASS (OR is supported, the JS store has none) |
| `{"$and":[{"$or":[...]},{"revision_id":{"$gt":102}}]}` nested | PASS |
| `{"$not":{"source_type":"wiki"}}` | PASS |
| `{"source_type":"wiki","document_id":"13"}` implicit AND | PASS |
| `{"source_type":"nope"}` | PASS, `[]` |
| `{}` or `None` | no filter |
| `{"source_type":{"$foo":"wiki"}}` | `ValueError: Invalid operator` (loud, not silent) |
| `topics` as `text[]`: `{"topics":"woodwinds"}` | ERROR `malformed array literal: "woodwinds"` |
| `topics` as `text[]`: `{"topics":{"$in":["woodwinds"]}}` | ERROR `could not find array type for data type text[]` |
| `topics` as `text[]`: `{"topics":{"$like":"%wood%"}}` | ERROR `operator does not exist: text[] ~~ unknown` |
| `topics` as `text[]`: `{"topics":["woodwinds"]}` | exact array equality only: matched Oboe (`['woodwinds']`) and not Cor anglais (`['woodwinds','instruments']`) |
| JSON-only table, `{"topics":{"$in":["woodwinds"]}}` | `[]` (compares text of the JSON array) |

Array contains on topics: NOT supported. Workaround verified (`a3.py`): store `topics` as one TEXT column in the form `"|woodwinds|instruments|"` and use `$like`:

```python
{"topics": {"$like": "%|woodwinds|%"}}                                   # contains one topic
{"$or":  [{"topics":{"$like":"%|woodwinds|%"}}, {"topics":{"$like":"%|brass|%"}}]}   # any of
{"$and": [{"topics":{"$like":"%|woodwinds|%"}}, {"topics":{"$like":"%|instruments|%"}}]}  # all of (JS store could not do this)
```

All three returned the correct rows. The JSON-only table also works with `{"topics":{"$like":'%"woodwinds"%'}}`. The `$or`/`$and` combination gives both ANY and ALL semantics. `aliases` does not need filtering (only the title line carries it), so keep `aliases` as `TEXT[]` for display or as JSON.

### A5. Search API

```python
vs.similarity_search(q, k=5, filter={...})
vs.similarity_search_with_score(q, k=5)
vs.similarity_search_with_relevance_scores(q, k=2)
vs.as_retriever(search_kwargs={"k":2, "filter":{"source_type":"encyclopedia"}}).invoke(q)
vs.as_retriever(search_type="mmr", search_kwargs={"k":2,"fetch_k":5,"lambda_mult":0.5,"filter":{...}}).invoke(q)
vs.max_marginal_relevance_search(q, k=3, fetch_k=5)
```

All PASS. Observed:
- Score is cosine DISTANCE, ascending: Oboe 0.4226, Cor anglais 0.5830, Tuba 0.8613, Cello 0.8613, Sonata form 0.8750. A self query returns 0.022 (float32 rounding). `similarity_search_with_relevance_scores` returns `1 - distance` (0.577 for the Oboe).
- Returned `Document.id` is the row UUID (`d.id`). `metadata` is rebuilt from the real columns plus the JSON column (without the embedding), with original types. Good for citations.
- Retriever `k` and `filter` are honoured. MMR works through the retriever (`['Oboe','Cor anglais']`) and directly.
- `k` defaults to 4, `fetch_k` 20, `lambda_mult` 0.5 (constructor arguments).

### A6. HNSW index, filters, iterative scan

```python
plain.apply_vector_index(HNSWIndex(m=16, ef_construction=64))   # 3.0 s on 3,000 rows
```

Generated: `CREATE INDEX "chunks_hlangchainvectorindex" ON "public"."chunks_h" USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')`. `is_valid_index()` returned True. Also available: `drop_vector_index`, `reindex`, `concurrently=True`, `IVFFlatIndex`, `partial_indexes`. 1536 dims fine. Unlike the JS helper, errors are not swallowed.

Filter interaction (3,000 rows, forced index scan with `enable_seqscan=off` via `connect_args={"options":"-c enable_seqscan=off"}`; at this size the default planner picks a sequential scan, same as in the JS spike):

| Filter (k=10) | rows returned, default | with `hnsw.iterative_scan=relaxed_order` |
|---|---|---|
| `document_id='10'` (10 of 3,000) | 0 | 10 |
| `revision_id between 10..14` (5 rows) | 0 | 5 |
| `source_type='wiki'` (25%) | 10 | 10 |
| no filter | 10 | 10 |

`HNSWQueryOptions(ef_search=400)` alone did not fix it (1 row and 0 rows). The library's built-in `HNSWQueryOptions` only supports `ef_search`, but `index_query_options` accepts any `QueryOptions` subclass whose `to_parameter()` returns a list of `name = value` strings. The library runs each as `SET LOCAL <option>` on the query connection:

```python
@dataclass
class HNSWIterative(QueryOptions):
    ef_search: int = 40
    iterative: str = "relaxed_order"
    max_scan_tuples: int = 20000
    def to_parameter(self): return [f"hnsw.ef_search = {self.ef_search}",
                                    f"hnsw.iterative_scan = {self.iterative}",
                                    f"hnsw.max_scan_tuples = {self.max_scan_tuples}"]
    def to_string(self): return "; ".join(self.to_parameter())
vs = PGVectorStore.create_sync(engine, emb, "chunks_h", metadata_columns=cols, index_query_options=HNSWIterative())
```

This worked (table above). So per-query GUCs ARE configurable, which the JS store could not do. Caveat: the options are applied only to the dense query in `__query_collection`. The sparse (keyword) query does not use HNSW, so it does not matter. Not verified: whether `SET LOCAL` within the library's connection scope is guaranteed to be on the same connection as the query in all pool configurations. It worked in these runs.

### A7. Hybrid search

```python
hc = HybridSearchConfig(tsv_column="content_tsv", tsv_lang="pg_catalog.english",
                        fusion_function=reciprocal_rank_fusion, fusion_function_parameters={"rrf_k": 60},
                        primary_top_k=20, secondary_top_k=20)
engine.init_vectorstore_table("chunks_h", 1536, metadata_columns=META, overwrite_existing=True, hybrid_search_config=hc)
vs = PGVectorStore.create_sync(engine, emb, "chunks_h", metadata_columns=cols, hybrid_search_config=hc)
vs.apply_hybrid_search_index()      # CREATE INDEX langchain_tsv_index ... USING gin (content_tsv), 0.02 s
vs.similarity_search("Neapolitan", k=5, filter={"source_type":"wiki"})
```

How the tsv column works: `init_vectorstore_table(..., hybrid_search_config=hc)` adds a plain `content_tsv tsvector NOT NULL` column (NOT a generated column). On every insert the library computes `to_tsvector('pg_catalog.english', :tsv_content)` in the INSERT and writes it (also in the upsert update clause). Consequence: the tsv column can only be populated through the library (or our own SQL that sets it); any other writer must also fill it or the NOT NULL constraint fails. `tsv_lang` is fixed per config (English). If `tsv_column` is left empty, the default name is `content_tsv`; if the table has no tsv column the library computes `to_tsvector` at query time (slow, no index).

The keyword query is `plainto_tsquery(lang, fts_query)` (AND of all words, no websearch syntax, no OR, no phrase) ordered by `ts_rank_cd`. The dense query is the normal `<=>` query. Both get the same filter. The two result lists are fused in Python by `fusion_function`. `reciprocal_rank_fusion(primary, secondary, rrf_k=60, fetch_top_k=4)` and `weighted_sum_ranking` (default, min-max normalised scores with weights) are provided. Each list is limited by `primary_top_k` and `secondary_top_k`, the final length is the call's `k`.

Results on 3,000 chunks (790 chars average, "Neapolitan" planted in three chunks revision_id 100, 1500, 2900, "Zeugma" in one, query vector deliberately unrelated):

| Test | Result |
|---|---|
| Hybrid "Neapolitan", useless vector, k=5 | Found two of three keyword hits in top 5 (100, 1500), three useless-vector rows mixed in. At k=10 all three (100, 1500, 2900) are present. With plain vector search, none. |
| Hybrid "Neapolitan" + `source_type="wiki"` | Only wiki rows returned (2860, 100, 2864, 1500, 1376) |
| Hybrid "Neapolitan" + `revision_id > 2000` | Only rows above 2000 (2865, 2900, 2863, 2860, 2864) |
| Hybrid "Neapolitan" + no-match filter | `[]` |
| Hybrid "Alias33" (alias exists only in the title line "Topic 33 (also: Alias33)") | Both Topic 33 chunks found (330, 333), so the alias title line works for keyword search |
| Plain vector search, useless vector, "Neapolitan" | Unrelated rows only |

Why only 2 of 3 at k=5: RRF is rank-only, so a keyword hit at sparse rank 3 scores `1/(60+2)`, the same as a useless dense hit at rank 3, and the ordering of ties falls to dict insertion order (dense first). With real embeddings this noise is smaller, but note that RRF has no weights. `weighted_sum_ranking` offers weights (`primary_results_weight`, `secondary_results_weight` through `fusion_function_parameters`), not tested.

STALE QUERY BUG (confirmed, important): `asimilarity_search` does `if hybrid_search_config and not hybrid_search_config.fts_query: hybrid_search_config.fts_query = query`, which mutates the config object stored on the vector store. All later queries on the same store reuse the FIRST query's keyword text:

```python
uv.similarity_search("Neapolitan", k=5)   # keyword part uses "Neapolitan" (correct)
uv.similarity_search("Zeugma", k=5)       # returned the SAME rows as "Neapolitan"; config.fts_query == 'Neapolitan'
```

Workaround verified: pass a fresh config copy per call, which the library reads from `kwargs["hybrid_search_config"]`:

```python
def hybrid(q, k=5, flt=None):
    c = copy.copy(hc); c.fusion_function_parameters = dict(hc.fusion_function_parameters)
    return vs.similarity_search(q, k=k, filter=flt, hybrid_search_config=c)
hybrid("Zeugma")   # now finds 777; hybrid("Neapolitan") finds 100, 1500
```

Alternatively, subclass or wrap the store. Without this, a chatbot would answer every question after the first with the first question's keywords. Also `fusion_function_parameters["fetch_top_k"]` is mutated in place on every call, so copy that dict too (done above).

Latency (3,000 chunks, 775 chars average after the title line, local Docker, fake embedding time included, 20 runs after warmup; `a4.py`):

| Operation | Median |
|---|---|
| Insert 3,000 chunks (6 calls of 500, includes hashing embeddings and tsv) | 7.2 s to 10.9 s (two runs) |
| Hybrid "Neapolitan" (k=5), no index | 27.5 ms |
| Hybrid "Neapolitan" + `source_type` filter, no index | 13.6 ms |
| Plain vector k=5 + filter, no index | 9.9 ms |
| After GIN (0.02 s) + HNSW (3.0 s) indexes: hybrid | 26.8 ms |
| same, hybrid + filter | 12.0 ms |
| same, plain vector + filter | 7.8 ms |

The index barely changes timings at 3,000 rows (planner uses a sequential scan). Insert is slow because `aadd_embeddings` loops and issues ONE INSERT ... ON CONFLICT plus commit per row on a new connection checkout (about 2.4 ms per row). The JS store did 3,000 in 1.3 s. For our corpus size a full re-ingest in a few tens of seconds is acceptable, but it is not transactional: a failure halfway leaves partial data. The hybrid dense query selects every column including the 1536-float embedding, and so does the sparse query (SELECT list is shared), so each hybrid call transfers up to 40 embeddings.

### A8. Surprises and blockers

- Nothing blocking. The deprecated-class question: the old `PGVector` class still exists in `langchain_postgres` (`langchain_postgres.vectorstores`, JSONB `langchain_pg_embedding` / `langchain_pg_collection` layout, different filter syntax). The new `PGVectorStore` (v2) is what the README recommends. Use `PGVectorStore` only.
- Engine lifecycle: `PGEngine.from_connection_string(url)` starts one background thread with its own asyncio loop (class-level, shared) and runs everything on it. Async methods (`asimilarity_search`, `aadd_documents`) work from FastAPI's loop because they hop to that thread (verified, 5 concurrent searches fine). The sync methods also work and can even be called inside a running loop (verified, they block the loop, so avoid in async handlers). A store created via `PGEngine.from_engine(create_async_engine(...))` has no background loop: async works, but sync methods raise `Engine was initialized without a background loop and cannot call sync methods.` Close with `await engine.close()`; not closing produced a psycopg ResourceWarning on exit.
- The URL must be a SQLAlchemy async URL: `postgresql+psycopg://` (psycopg3, tested) or `postgresql+asyncpg://`. A plain `postgresql://` URL (as used by the LangGraph checkpointer) does not work for `PGEngine`. Two URL styles in the same app.
- Required column names: none fixed, but the defaults are `langchain_id`, `content`, `embedding`, `langchain_metadata` (not `id`, `metadata`). The store validates the table at `create`/`create_sync` (content must be text, embedding must be vector).
- Metadata columns must be listed both when creating the table and when opening the store. Forgetting them in the second place turns them into JSON-only keys (they still filter via JSON but with cast rules) and the real columns come back empty.
- `distance_strategy` default is cosine. `index_query_options` is per store, and `k`, `fetch_k`, `lambda_mult` are constructor defaults.
- Filter field names must be identifiers (`[A-Za-z0-9_]`); values are bound parameters; table and column names are interpolated into SQL from trusted constants.
- Not tested: concurrent writers, `ignore_metadata_columns`, `weighted_sum_ranking` weights, `from_texts`, very large tables, sparse query with `tsv_column` omitted, real embeddings.

## Part B: music library for the five tools

### Candidates and licences (read from package metadata with `importlib.metadata`, today's PyPI data)

| Package | Version | Last release | Licence (metadata) | Install size (site-packages, minus 15 MB of venv baseline) | Import time |
|---|---|---|---|---|---|
| `music21` | 10.5.0 | 2026-06-17 | BSD-3-Clause | about 230 MB (numpy, matplotlib, scipy-free, joblib, requests, jsonpickle, webcolors, chardet) | 1.4 s |
| `pychord` | 1.4.1 | 2026-10-09 | MIT | under 1 MB, zero runtime dependencies | 0.008 s |
| `mingus` | 0.6.1 | 2020-12-31 | GPLv3 | under 1 MB (needs `six`) | 0.007 s |
| `musthe` | 1.0.0 | 2018-07-06 | MIT | tiny | not run |
| `pytheory` | 0.57.13 | 2026-07-07 | MIT | about 150 MB (scipy, sounddevice, rich) | 0.05 s to 0.5 s |

Findings on candidates: `mingus` is GPLv3 and unmaintained for almost six years, so it is disqualified for our use even though its output was fine (it was run for comparison: `determine(["D","F","A","C"])` gave `['Dm7','FM6','FM|Dm']`). `musthe` is MIT but untouched since 2018, not tested. `pytheory` is a young one-person project (v0.57) that pulls in scipy and sounddevice (PortAudio); it worked for most cases but gives a single chord candidate, `Key.detect` returned None, and intervals come back as strings like `'perfect 5th + 1 octave'` with no semitone count. Not recommended as a dependency. The two to rely on are `music21` and `pychord`.

### Results: the same cases `tonal` passed (real output)

Legend: tonal expected value in column 2.

| Case | tonal (expected) | `music21` 10.5.0 | `pychord` 1.4.1 |
|---|---|---|---|
| C major scale notes | C D E F G A B | PASS `['C','D','E','F','G','A','B']` | no scale API |
| D dorian | D E F G A B C | PASS `['D','E','F','G','A','B','C']` (`scale.DorianScale('D')`) | no scale API |
| Cmaj7 notes | C E G B | PASS `harmony.ChordSymbol('Cmaj7').pitches` gives `C E G B` | PASS `Chord("Cmaj7").components()` gives `['C','E','G','B']`, with octaves `['C4','E4','G4','B4']` |
| Interval C4-G4 | 5P, 7 semitones | PASS `('P5','Perfect Fifth', 7)` | no interval API |
| Interval C4-G5 | 12P / compound, 19 st | PASS `('P12','Perfect Twelfth', 19)`; `simpleName` `P5`, `generic.undirected` 12 | no interval API |
| Transpose Dm7 up P5 | Am7 | PASS `ChordSymbol('Dm7').transpose('P5').figure` gives `Am7` | PASS `c=Chord("Dm7"); c.transpose(7)` gives `Am7` (semitones, in place, not interval-aware) |
| Detect D F A C | [Dm7, F6/D] | PARTLY: one answer only. With pitch names without octaves it returns root D, bass C, `Dm7/C`; with ascending octaves `['D4','F4','A4','C5']` it returns `Dm7`. No candidate list (trying each note as root gave `Dm7` every time). `ChordSymbol('F6/D')` is recognised as "enharmonic equivalent to minor seventh chord". | PASS `find_chords_from_notes(["D","F","A","C"])` gives `[<Chord: Dm7>, <Chord: F6/D>]`, identical to tonal |
| Detect C E G B | [Cmaj7] | PASS `Cmaj7` (root C, `major seventh chord`) | PASS `[<Chord: CM7>]` (it prints `CM7`, and `Chord("Cmaj7") == Chord("CM7")` is True) |
| Key signature D major | 2 sharps | PASS `key.Key('D').sharps == 2`, altered `['F#','C#']` | no key API |
| Key signature Eb major | 3 flats | PASS `key.Key('E-').sharps == -3`, altered `['B-','E-','A-']` (`Key('Eb')` also accepted) | no key API |
| Note to MIDI (C4) | 60 | PASS `note.Note('C4').pitch.midi == 60` | no |
| A4 frequency | 440 | PASS `pitch.Pitch('A4').frequency == 440.0` | no |
| 450 Hz to nearest note + cents | A4 +39 | PARTLY: `p = Pitch(); p.frequency = 450` gives `A~4` (quarter-tone sharp A) and `microtone.cents == -11.1`. This is relative to the quarter tone, not to A4. Correct recipe: `nearest = round(p.ps)` gives A4, `cents = (p.ps - nearest) * 100` gives `+38.9`. | no |
| Written C4 on Bb clarinet sounds Bb3 | Bb3 | PASS `instrument.Clarinet().transposition` is `M-2` (there is no `BFlatClarinet`), `note.Note('C4').transpose(M-2).nameWithOctave` gives `B-3` (Bb3). Also `Note('C4').transpose(-2)` gives `B-3` (flat spelling chosen automatically). Instrument table: Clarinet M-2, BassClarinet M-9, Trumpet M-2, AltoSaxophone M-6, English Horn P-5, Horn P-5. | `Chord("C").transpose(-2)` gives `Bb` (chords only; no single-note support). |
| Invalid `'H4'` | tonal: empty, no throw | EXCEPTION: `PitchException: Cannot make a step out of 'H'`. `ChordSymbol('H4')` gives `ValueError: Chord H4 does not begin with a valid root note.` | EXCEPTION `ValueError: Invalid note H` (`Chord("H4")`), `note_to_val("H")` gives `ValueError: Unknown note H` |
| Invalid `'Xyz'` | tonal: empty, no throw | EXCEPTION: `PitchException: Cannot make a step out of 'X'` (Note, Pitch, Key, Scale, Chord), `ValueError` for `ChordSymbol` | EXCEPTION `ValueError: Invalid note X`. Also `Chord("Cxyz")` gives `ValueError: Unknown quality: xyz`. `find_chords_from_notes(["D4","F4",...])` gives `ValueError: Unknown quality: 4m7` (note names only, no octaves). |

Invalid input behaviour: both libraries raise (unlike `tonal`, which returns empty). That is easy to wrap (`try/except ValueError`, `music21` raises `PitchException`, a subclass of its own `Music21Exception`), and arguably better for a tool that must return an error message to the LLM. Python sample output verified for `Eb` spelling: `Key('Eb')` and `MajorScale('Eb')` accept `Eb`; music21's own output spells flats as `-` (`B-`, `E-`), so a formatting step (`-` to `b`) is needed before output.

Install size and import time: `music21` 230 MB and 1.4 s (matplotlib and numpy come along even though we do not use them), `pychord` effectively free and 8 ms. Docker image impact only matters if the image is tight; a 230 MB dependency in a backend container is acceptable but heavy for what we use.

API awkwardness:
- `pychord`: tiny, string based, pleasant (`Chord("Dm7")`, `.components()`, `.transpose(n)`, `find_chords_from_notes([...])`). Gotchas: `transpose` mutates in place and takes semitones; its spelling choice is simple (`Cm7` -2 gives `Bbm7`, `D` +2 gives `E`, `Dm7` +3 gives `Fm7`, optional `scale` argument controls sharps versus flats); `find_chords_from_notes` accepts note names without octaves only; output names use `M7` style. 104 chord qualities. No notion of enharmonic respelling or inversion bass beyond `/` slash chords. Active (release 9 days before the test date).
- `music21`: powerful but verbose and heavy: object graph (`Note`, `Pitch`, `Interval`, `ChordSymbol`), flats written `-`, octave-less chord input produces misleading inversions (`Dm7/C`), no multi-candidate detection, frequency-to-note needs a manual cents calculation. Only library here with proper diatonic interval naming (`P12`, `M-2`) and instrument transposition tables.

### Verdict for the five tools

| Tool | Best option | Library coverage |
|---|---|---|
| `chord_info` | `pychord` (components, name, quality) | Yes, MIT. `music21.harmony.ChordSymbol` as a fallback. Detection of ambiguous chords (Dm7 vs F6/D) works only in `pychord`. |
| `scale_info` | `music21` scales, or a hand-written table | `music21` covers major, minor, modes, and many more. A hand-written dict of about 20 scales as semitone patterns plus note spelling is about 40 lines. |
| `interval_between` | `music21.interval.Interval` | Quality, size, semitones, compound all correct. Hand-written is possible (about 40 lines: letter distance for size plus semitones for quality), but spelling rules are fiddly. |
| `transpose_for_instrument` | hand-written (a table of instrument to semitone offset) plus `music21` `Note.transpose` for spelling | `music21` has transposition for about 10 instruments (Clarinet M-2 and so on). The offset table is data we want to own anyway (curated, citable). Semitone arithmetic is trivial; spelling (Bb3 not A#3) needs a flats/sharps choice or `music21`. |
| `note_frequency` | hand-written | `440 * 2**((midi-69)/12)`, note name to midi, nearest note and cents from a frequency: about 15 lines. No library does it better. `music21` works but needs the manual cents recipe above. |

Answer: partly. No Python library replaces `tonal` end to end. `pychord` (MIT, zero dependencies, active) fully matches `tonal` for chord info, transposition and ambiguous chord detection. For scales, intervals, key signatures and instrument transposition, `music21` (BSD) is the only credible library and it is heavy and sometimes awkward. A pragmatic split: use `pychord` for chords, write `note_frequency` and the instrument offset table by hand, and either add `music21` for scale and interval spelling or hand-write `scale_info` and `interval_between` (about 100 lines total with tests). If we do not want a 230 MB dependency, the hand-written route plus `pychord` is viable. If we want exactly `tonal`'s breadth (modes, `Scale.detect`, roman numerals, progressions), only `music21` comes close, so the JS `tonal` stays the better fit for that breadth.

## Part C: agent plumbing with fakes

### C1. `create_agent` with a fake tool-calling model and Postgres checkpointer

Fake model (`fakes.py`, a custom `BaseChatModel`): after each user message it emits a `scale_info` tool call, then a `note_frequency` tool call, then a final answer that states how many user messages it can see. It implements `_generate`, `_stream` (token by token, tool call as a `tool_call_chunk`, final chunk with `usage_metadata`) and `bind_tools` (returns itself). `GenericFakeChatModel` was not used because it has no `bind_tools`. Tools use `@tool` and `get_stream_writer()`.

```python
from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver
with PostgresSaver.from_conn_string("postgresql://postgres:spike@localhost:54330/postgres") as saver:
    saver.setup()
    agent = create_agent(FakeToolModel(), tools=[scale_info, note_frequency],
                         system_prompt="You are Sound Companion.", checkpointer=saver)
    cfg = {"configurable": {"thread_id": "t-1"}}
    agent.invoke({"messages": [{"role":"user","content":"What are the notes of C major?"}]}, cfg)
    agent.invoke({"messages": [{"role":"user","content":"And the frequency of A4?"}]}, cfg)
    state = agent.get_state(cfg)       # StateSnapshot
```

Output:

```
TURN 1 final: I can see 1 user message(s): ['What are the notes of C major?']. The scale is C D E F G A B and A4 is 440 Hz.
TURN 2 final: I can see 2 user message(s): ['What are the notes of C major?', 'And the frequency of A4?']. ...
get_state: next=() n_messages=12 checkpoint_id=1f1cbf4f-...
  human, ai(tool_calls=[scale_info]), tool, ai(tool_calls=[note_frequency]), tool, ai(final), human, ai, tool, ai, tool, ai(final)
state history entries: 14
OTHER THREAD (thread_id="other") sees: 1 user message(s)   (isolated)
```

PASS: the second turn sees the first turn's messages; `agent.get_state(cfg).values["messages"]` returns the full list (typed `HumanMessage`, `AIMessage` with `tool_calls` and `usage_metadata`, `ToolMessage`), which is what an export endpoint needs. `get_state_history` lists checkpoints (14 for 2 turns).

Tables created by `setup()` (schema `public`): `checkpoints` (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, `checkpoint jsonb`, `metadata jsonb`), `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` (10 versions, 0 to 9). `setup()` is idempotent (re-run on existing tables was fine).

Async variant: `AsyncPostgresSaver.from_conn_string(url)` as `async with`, `await saver.setup()`, `agent.astream` / `aget_state` all worked. Notes:
- One `AsyncPostgresSaver.from_conn_string` holds a single connection. For a web server use `AsyncConnectionPool(url, kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})` and `AsyncPostgresSaver(pool)` (used in the FastAPI app below). The `autocommit=True` and `dict_row` kwargs are required; the saver also requires the psycopg3 plain URL (`postgresql://`), not the SQLAlchemy `+psycopg` URL used by `PGEngine`.
- The sync and async savers each worked against the same tables. One cosmetic message was seen once on an aborted run: `error ignored in rollback on <psycopg.AsyncConnection ...>: connection not in pipeline mode` (only when my script raised inside the `async with`).
- The `PostgresSaver` checkpoint tables do not touch our chunk tables; thread messages are in `checkpoint_blobs` / `checkpoints.checkpoint`, so exporting a conversation should go through `agent.get_state` and not raw SQL.

### C2. Streaming with `stream_mode=["messages","updates","custom"]`

`agent.astream(input, cfg, stream_mode=[...])` yields `(mode, data)` tuples. Real output for one turn (fake model, node names `model` and `tools` in this LangChain version):

```
[messages] AIMessageChunk content='' tool_call_chunks=[{'name':'scale_info','args':'{"root": "C", "scale": "major"}','id':'call_1_1','index':0}] node=model
[messages] AIMessageChunk content='' usage={'input_tokens':10,'output_tokens':5,'total_tokens':15} node=model       <- last chunk carries usage
[updates ] node=model -> ai tool_calls=[('scale_info', {'root':'C','scale':'major'})]                              <- complete tool call here
[custom  ] {'type': 'citations', 'items': [{'title': 'Scale (music)', 'url': 'https://example.org/scale', 'license': 'CC BY-SA 4.0'}]}
[custom  ] {'type': 'queries', 'items': ['scale C major']}
[messages] ToolMessage content='C D E F G A B' tool_call_id='call_1_1' name='scale_info' node=tools                 <- tool result
[updates ] node=tools -> tool:'C D E F G A B'
... second tool the same way (custom event {'type':'progress','message':'computing A4'}) ...
[messages] AIMessageChunk content='I ' node=model   [messages] AIMessageChunk content='can ' ... (one chunk per token)
[messages] AIMessageChunk content='' usage={...}     [updates ] node=model -> ai:"I can see 1 user message(s) ..."
```

Mapping to typed SSE events:
- `token`: `messages` mode, `AIMessageChunk` with non-empty `content`, node `model`. (With real providers, `content` may be a list of blocks; handle both.)
- `tool_call`: from `updates` (node `model`, `AIMessage.tool_calls`, complete name and args). The `messages` stream only has partial `tool_call_chunks` (args as incremental JSON strings with a real provider), so use `updates` for a clean event.
- `tool_result`: `updates` (node `tools`, `ToolMessage`) or the `messages` mode `ToolMessage` (has `tool_call_id`, `name`).
- `citations`, `queries`, progress: `custom` mode. A tool calls `get_stream_writer()` and writes any dict; it arrives unchanged. We put a `"type"` field in the dict and forward it as is (verified: `get_stream_writer` works inside a `@tool` in an async agent). The `custom` writer only works when the tool runs inside a LangGraph run (an agent), not when called directly.
- `usage`: `usage_metadata` on the last chunk of each model call (sum them for the turn; the fake emitted 10/5/15 per call and the app reported 30/15/45 for 3 model calls). Real value depends on the provider (see C4).
- Not covered by the fake: the final text also appears as one complete `AIMessage` in the `updates` event, so tokens do not need to be buffered for persistence (checkpointer stores them).

### C3. FastAPI SSE endpoint

`app.py` (condensed; full file in the scratchpad):

```python
@asynccontextmanager
async def lifespan(app):
    async with AsyncConnectionPool(PG_URL, max_size=5, open=False,
               kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}) as pool:
        saver = AsyncPostgresSaver(pool); await saver.setup()
        app.state.agent = create_agent(model, tools=[...], checkpointer=saver)
        yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["POST","GET"], allow_headers=["content-type"])

def sse(event): return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

@app.post("/api/chat")
async def chat(req: ChatReq):               # {thread_id, message}
    async def gen():
        async for mode, data in agent.astream({"messages":[...]}, cfg, stream_mode=["messages","updates","custom"]):
            ...  # yield sse({"type":"token"|"tool_call"|"tool_result"|<custom type>, ...})
        yield sse({"type":"usage", ...}); yield sse({"type":"done"})
    return StreamingResponse(gen(), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})
```

Run: `uvicorn app:app --port 8765`, then `curl -sN -i -X POST localhost:8765/api/chat -H 'content-type: application/json' -d '{"thread_id":"sse-1","message":"notes of C major?"}'`. Real output:

```
HTTP/1.1 200 OK
cache-control: no-cache
x-accel-buffering: no
content-type: text/event-stream; charset=utf-8
Transfer-Encoding: chunked

data: {"type": "tool_call", "id": "call_1_1", "name": "scale_info", "args": {"root": "C", "scale": "major"}}

data: {"type": "citations", "items": [{"title": "Scale (music)", "url": "https://example.org/scale", "license": "CC BY-SA 4.0"}]}

data: {"type": "queries", "items": ["scale C major"]}

data: {"type": "tool_result", "id": "call_1_1", "name": "scale_info", "content": "C D E F G A B"}

data: {"type": "tool_call", "id": "call_1_2", "name": "note_frequency", "args": {"note": "A4"}}

data: {"type": "progress", "message": "computing A4"}

data: {"type": "tool_result", "id": "call_1_2", "name": "note_frequency", "content": "440.0 Hz"}

data: {"type": "token", "text": "I "}
data: {"type": "token", "text": "can "}  ... (one event per token) ...
data: {"type": "usage", "input_tokens": 30, "output_tokens": 15, "total_tokens": 45}

data: {"type": "done"}
```

(Blank lines between token events omitted above for brevity.) A second and third `curl` with the same `thread_id` showed `3 user message(s): ['notes of C major?', 'second question', 'third']`, so checkpointer memory works through the HTTP endpoint with a connection pool. An invalid body returns 422 JSON before streaming starts.

CORS (verified with `curl -X OPTIONS`): from `Origin: http://localhost:5173` the preflight returned `200`, `access-control-allow-origin: http://localhost:5173`, `access-control-allow-methods: POST, GET`, `access-control-allow-headers: ... content-type`. An unlisted origin got `400 Bad Request` on the preflight. A React dev server (Vite, `:5173`) calling `http://localhost:8000` directly needs `CORSMiddleware`. Note `fetch()` with a POST body, as needed for SSE (the browser `EventSource` is GET only and cannot send a JSON body, so use `fetch` + `ReadableStream` or a library like `@microsoft/fetch-event-source`), always triggers a preflight for `content-type: application/json`.

Avoiding CORS: use a Vite dev proxy so the browser only talks to its own origin. `vite.config.ts`: `server: { proxy: { "/api": "http://localhost:8000" } }`. In production serve the frontend and `/api` behind the same reverse proxy. This was not run (no Vite setup in this spike).

Proxy buffering gotchas (documented behaviour, NOT tested through a real proxy):
- nginx buffers responses by default: needs `proxy_buffering off;` for the `/api/chat` location, or the `X-Accel-Buffering: no` response header (set in the app above), plus `proxy_read_timeout` large enough, `proxy_http_version 1.1`, no gzip on `text/event-stream`.
- Do not add `GZipMiddleware` to the streaming route (it buffers).
- Idle timeouts at load balancers and proxies (often 60 s): emit a comment line `: keepalive\n\n` every 15 to 20 s while tools run.
- The Vite dev proxy (http-proxy) streams by default. Some corporate proxies buffer.
- Client disconnect: Starlette cancels the generator (`asyncio.CancelledError`), which cancels the agent run; the checkpoint may then hold a partial turn (a tool call without a result). Not tested here; a real test is worthwhile.
- The fake model emits tokens instantly, so true incremental delivery (first byte timing) was not measured with `curl`. The `Transfer-Encoding: chunked` response and per-event writes indicate it will stream, but a real slow model is the real test.

### C4. Live run against OpenRouter (2026-10-21)

Run with the author's real key, `langchain-openai 1.7.2`, `langchain 1.4.6`, `langchain-core 1.6.12`, `langgraph 1.2.16`, `openai 3.35.1`, models `openai/gpt-4o-mini` and `openai/text-embedding-3-small`, base URL `https://openrouter.ai/api/v1`. Throwaway scripts (not in the repo); total spend a small fraction of a cent.

| Check | Result |
|---|---|
| Real chat call and real embedding call | PASS. Chat returned `pong`, embedding has 1536 dimensions. Both models were allowed by the key's workspace. |
| 1. Streamed token counts (`stream_usage=True`) | PASS. `usage_metadata` arrives on the second-to-last chunk (the one carrying `finish_reason`), followed by one empty chunk. Take usage from the aggregated message, not from the last chunk. |
| 2. `usage.cost` survives `langchain-openai` | **Non-streamed: PASS**, it is in `response_metadata["token_usage"]["cost"]` (plus `cost_details`, `is_byok`). **Streamed: FAIL**, it is dropped. The raw SSE usage chunk does carry `cost`; the converted chunk only gets token fields. |
| 3. Usage chunk survives `create_agent` streaming | PASS. `stream_mode="messages"` shows `usage_metadata` for every model call in a turn, and the final `AIMessage` in `updates` has it too. |
| 4. Cost across several model calls in one turn | PASS with the subclass below. A turn with a tool call and an answer was two model calls, 2.22e-05 each (72/19 and 100/12 tokens, matching $0.15 and $0.60 per million), summed to 4.44e-05. |
| 5. Tool-call fragments with real streaming | PASS. The arguments arrived as 13 `tool_call_chunks` fragments; the `updates` event still held the complete call (`add {'a': 1234, 'b': 4321}`). |
| 6. Streamed vs non-streamed totals | PASS. Same tokens (15 and 5) and same cost (5.25e-06) for the same prompt. |

**Chunk ids.** The streamed chunks carry LangChain's own id (`lc_run--...`), not OpenRouter's `gen-...` id, and `response_metadata` has no `id`.

**Generation lookup.** `GET /api/v1/generation?id=<gen id>` returned 404 on four tries over about 8 seconds, even with the id taken from the raw stream. It is not usable as the primary cost source.

**Metadata merge gotcha.** When chunks are added, string values in `response_metadata` are concatenated (observed: `finish_reason` became `stopstop`, `model_name` was doubled). Put a new key on one chunk only.

**Fix that works** (subclass, overrides the private `_convert_chunk_to_generation_chunk`, so pin `langchain-openai`):

```python
class CostChatOpenAI(ChatOpenAI):
    def _convert_chunk_to_generation_chunk(self, chunk, default_chunk_class, base_generation_info):
        gen = super()._convert_chunk_to_generation_chunk(chunk, default_chunk_class, base_generation_info)
        usage = chunk.get("usage")
        if gen is not None and usage and "cost" in usage:
            gen.message.response_metadata["token_usage"] = usage
            gen.message.response_metadata["generation_id"] = chunk.get("id")
        return gen
```

With it the aggregated stream and the agent's per-call `AIMessage` both carry `response_metadata["token_usage"]["cost"]`, so story 11 reads the cost from the same place for streamed and non-streamed calls.

Not checked by this run (the author's to confirm on the account): credits equal USD on the account page, and that the workspace guardrails are meant to allow the two models.

### C5. Real model through `create_agent` with the search tool (Story 5, issue 30)

`ChatOpenAI` (`openai/gpt-4o-mini`, OpenRouter base URL, `temperature=0`) with `create_agent(model, tools=[search_knowledge_base], system_prompt=...)`, run with `scripts.ask`. Same versions as C4 (`langchain-openai 1.7.2`, `langchain 1.4.6`, `langgraph 1.2.16`).

- **Tool call shape:** one `AIMessage.tool_calls` entry, `{'name': 'search_knowledge_base', 'args': {'query': ..., 'source_type': 'encyclopedia'}}`, then a `ToolMessage` with our formatted chunks, then the final `AIMessage`. The `Literal` `source_type` in the args schema is passed through correctly. An invalid value is turned into an error message by `handle_validation_error` and does not raise.
- **Citing:** "How does a clarinet produce sound?" gave a grounded answer naming `(Clarinet > Acoustics)` and ending with the page link and licence. With a first prompt that said "cite every claim", the model cited once at the end; asking for the cite right after each claim, not only at the end, gave a cite per paragraph.
- **Surprise:** the model set `source_type='encyclopedia'` on its own although the tool description says to leave filters out unless asked. It was harmless here, but a wrong guess would hide textbook pages. Watch it in the tool-calling eval (Story 9) and tighten the description if it keeps happening.
- **Off topic:** "Tell me a joke" got a polite decline and no tool call.
- **Cost:** about 2,600 chat tokens for one grounded answer, a few hundredths of a cent.
- **Fake model in tests:** `GenericFakeChatModel` has no `bind_tools`, so the tests subclass it (declare the extra fields, pydantic rejects unknown attributes).

### C6. Memory per thread with a real model (Story 5, issue 31)

`AsyncPostgresSaver` on `AsyncConnectionPool(url, kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}, open=False)`, used as `async with` in `app/agent/memory.py`, with `await saver.setup()` on every start. Run with `scripts.chat`.

- **Pool settings:** the three kwargs were enough, with the plain `postgresql://` URL (`settings.database_url`), not the SQLAlchemy one. `setup()` is safe to repeat. It created `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` and `checkpoint_migrations`; `alembic check` still reports no drift because `include_object` in `env.py` ignores tables that are not in our models.
- **Follow-up:** after "How does a clarinet produce sound?", "and what are its registers?" in the same thread was searched as `clarinet registers` and answered from the Clarinet page, so the model used the earlier turn.
- **`aget_state`:** `state.values["messages"]` holds every message of the thread in order: `HumanMessage`, `AIMessage` with `tool_calls` (empty content), `ToolMessage` with our formatted chunks, final `AIMessage`. The retrieved chunks are part of the thread, so history grows by about one search result per turn. After two turns the thread had 15 checkpoint rows.
- **Isolation:** two threads do not share messages (unit test with a fake model, and `--history` on the real thread shows only its own turns).
- **Surprise:** in a new thread, "and what are its registers?" with nothing before it was searched as "registers of the clarinet" and answered, instead of asking what "its" refers to. The model guessed a referent that was nowhere in the thread. Rule 5 (ask when unclear) in the prompt did not stop it. This is for the clarify checks (q15 to q17) and the Story 9 eval, not a memory bug.
- **Tests:** an `InMemorySaver` is enough to test that a second turn sees the first and that threads are separate, no database needed.

### C7. Clarify, decline and empty retrieval with a real model (Story 5, issue 32)

`scripts.check_behaviour` runs each case on its own in-memory thread and prints tool calls and answers (a person judges them, Story 9 automates it). `openai/gpt-4o-mini`, `temperature=0`.

| Case | First prompt (rules only) | Final prompt (rules plus 3 worked examples) |
|---|---|---|
| q15 "Tell me about the guitar." | Answered, listed two types | One question: "Which type of guitar do you mean: classical, steel-string acoustic, electric, or another kind?" The reply "electric" is answered from the Electric guitar page |
| q16 range of a saxophone | Answered with the alto range | Asks soprano, alto, tenor or baritone |
| q17 "Transpose it up a fifth." | Asked what to transpose, no tool call | Same (one version declined it as off-topic, and one copied the wording of an example) |
| q02, q04, q05, q13 specific questions | Answered with cites | Answered with cites, no question |
| "Tell me a joke", pancake recipe | Declined, no tool call | Same |
| "How do I tune a theremin?" | States the knowledge base has nothing on it | Same, one line, no answer from memory |

- **What changed the behaviour:** rewording rule 5 as a checklist ("after searching, before answering, if one case fits your whole reply is one question") made q16 work and q17 worse. What fixed q15 and q16 was three worked examples with other subjects (drum, clarinet range, "play it an octave lower") plus "ask even when the pages already describe the kinds, do not summarise them". Examples must say the reply is a question about the user's own request, or the model copies their wording.
- **Surprise:** the Guitar page has a "Types" section, so for "guitar" the model treats the question as answered. A search for "guitar" returns only chunks of the Guitar page, never the Classical, Electric or Bass guitar pages, so the options come from section text and the model's wording, and the question did not name the bass guitar. Retrieval cannot yet list which pages exist on a subject (hybrid search or a title listing would help).
- **Judging by eye:** the empty-retrieval case needs a topic the Corpus truly lacks, "tune a theremin" works. "Range of a sousaphone" is covered by the Sousaphone page, so the answer there is grounded.
- **Cost:** about a cent for the whole run of ten cases.

## Recommendation

The Python stack is good enough for this project, with a few small workarounds. On the evidence of this spike it is better than the TypeScript store on ingest and filters, and roughly equal on hybrid search (library hybrid exists but has a bug to wrap).

Verdict by area:
- Vector store (`langchain-postgres` `PGVectorStore`): usable. Upsert by id, delete by filter that refuses an empty filter, `$and/$or/$not`, numeric comparison, MMR, HNSW creation helper, hybrid search with a built-in RRF, per-query HNSW settings via `index_query_options`.
- Agent plumbing: `create_agent` plus `AsyncPostgresSaver` plus FastAPI SSE works, and event mapping for token, tool_call, tool_result, citations, queries and usage is straightforward.
- Music tools: needs a split between `pychord`, `music21` and about 100 lines of hand-written code (details in Part B).

Workarounds needed:
1. Hybrid config mutation bug: always pass a fresh `HybridSearchConfig` copy (and a copied `fusion_function_parameters`) per call via the `hybrid_search_config=` keyword, or wrap the store in a small class that does it. Add a regression test with two successive different queries. Without it every query after the first reuses the first keyword text.
2. Topics filtering: store `topics` as a pipe-delimited TEXT (`|woodwinds|instruments|`) and filter with `$like` combined with `$or`/`$and`. Native `text[]` columns do not filter.
3. Iterative scan: pass a custom `QueryOptions` subclass (`hnsw.iterative_scan = relaxed_order`) as `index_query_options`. Re-test with the real corpus size before enabling HNSW; at about 3,000 rows Postgres uses a sequential scan anyway.
4. Ingest speed: one INSERT plus commit per row (7 to 11 s for 3,000 chunks) and no transaction around a batch. Acceptable for a few thousand chunks. For atomic re-ingest, wrap delete-by-document plus add in our own transaction or accept eventual cleanup. A bulk path via our own SQL with `executemany` is possible if it becomes a problem.
5. Two URL styles: `postgresql+psycopg://` for `PGEngine`, plain `postgresql://` with `autocommit=True` and `dict_row` for the checkpointer pool. Isolate both in one config module.
6. `similarity_search_*` scores are cosine distance (lower is better); convert with `1 - distance` for display.
7. Metadata column names must be declared in two places (table creation and `create_sync`); keep one constant list.
8. SSE: add keepalive comments, `X-Accel-Buffering: no`, the Vite dev proxy for dev (no CORS code needed), and a fetch-based client (POST body) instead of `EventSource`.

Music library decision: use `pychord` (MIT) for `chord_info` (including ambiguous detection, matching `tonal`'s `[Dm7, F6/D]`) and chord transposition. Hand-write `note_frequency` and the instrument offset table for `transpose_for_instrument` (data we want to curate and cite anyway). For `scale_info` and `interval_between`, choose between `music21` (BSD, correct spelling, 230 MB, 1.4 s import) and a small hand-written module (about 100 lines with tests, spelling rules are the only tricky part). Do not use `mingus` (GPLv3, last release 2020) or `musthe` (2018). `pytheory` is too young and heavy. If we want `tonal`'s exact breadth with little code, staying with the JS library for the tools is the lower-effort path.

Biggest risks:
1. The hybrid state bug is easy to miss and quietly returns wrong results; it needs a regression test. Pin `langchain-postgres` to an exact version (0.0.19 is a 0.0.x release, so the API can move).
2. Music tools are the weakest link in Python: no single library, and `music21` is heavy. Budget about a day to write and test the hand-written parts against the same golden cases as `tonal`.
3. Everything about real model behaviour is untested: OpenRouter usage and cost on streams, real token streaming latency through proxies, partial checkpoints after a client disconnect, tool-call argument streaming. The fake model does not exercise these.
4. Insert speed and non-transactional batches could hurt if the corpus grows by an order of magnitude.
5. Not tested: very large tables, real embeddings (hybrid ranking quality with RRF under real vectors), weighted-sum fusion, concurrent ingest, Windows event loop issues for the async saver (the docs mention a selector loop requirement on Windows only; this machine is macOS).

### C6. SSE endpoint with a real model (Story 6, issue 35)

`POST /api/chat` (`app/api/chat.py`, adapter in `app/agent/streaming.py`) run with `uvicorn` against OpenRouter (`openai/gpt-4o-mini`), `curl -N`, with a timestamp on each line.

**Incremental streaming.** Passes. For "How does a clarinet produce sound?": headers at +0 s, `tool_call` at +0 s, `tool_result` at +0.6 s (the search), first `token` at +1.3 s, then 200+ one-word `token` events spread over about 4 s, then `done`. Response headers were `cache-control: no-cache` and `x-accel-buffering: no`. A search was fast here, so the `: keepalive` comment never fired live; it is covered by a unit test with a short interval.

**Disconnect mid-stream** (curl cut after 2 s, then the checkpoint read with `saver.aget_tuple`):
- Cut while the answer streamed: the checkpoint held `human`, `ai` (tool call) and `tool` (result), no final `ai` message. Step 2, source `loop`.
- Cut before the first token (0.4 s): only the `human` message.
- The next message on the same thread worked, and the saved history then had both turns, the first one without an answer. So the thread stays usable, with an unanswered question in its history (decision 57).

**Bug found, then removed.** The first hand-written keepalive wrapper called `aclose()` on the event generator while a cancelled `__anext__` was still running: `RuntimeError: aclose(): asynchronous generator is already running` in the server log on every disconnect. The keepalive and SSE formatting now come from `sse-starlette` (default `\r\n` line ends overridden with `sep="\n"` on the response and each event), and the log is clean on disconnect.

**Mapping notes.** `tool_call` and `tool_result` come from `updates`, `token` from `messages` (node `model`), `custom` dicts with a `type` are forwarded unchanged. `durationMs` is measured between the `tool_call` and `tool_result` events, so it includes the graph's own overhead. A failure in the run is logged with its traceback and sent as `{"type":"error","code":"agent_error"}` with a fixed message, so provider text is not leaked, and no `done` follows.
