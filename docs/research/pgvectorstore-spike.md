# PGVectorStore (LangChain.js) spike

> **Status note:** this is the TypeScript spike, kept as context for the archived stack ([../archive/typescript-stack/](../archive/typescript-stack/)). The current backend is Python, see [python-stack-spike.md](python-stack-spike.md).

Date: 2026-10-19. Tested against a throwaway `pgvector/pgvector:pg16` container (pgvector 0.8.7), Node v24.21.0, plain ESM scripts (`"type": "module"`), fake deterministic 1536-dim embeddings (token-hash bag, L2-normalised; no API keys, no paid calls). The container was removed afterwards (`docker rm -f pgvspike`). Scripts live in the session scratchpad (`.../scratchpad/spike/`: `common.mjs`, `t1.mjs`, `t4.mjs`, `t6.mjs`, `t7.mjs`, `t7b.mjs`, `t7c.mjs`). Not tested: TypeScript compilation (only plain ESM JS), real embedding models, tables much larger than 3,000 rows.

## Verdict

| # | Item | Verdict | Note |
|---|------|---------|------|
| 1 | Install and ESM on Node 24 | PASS | `@langchain/pgvector@0.1.0`, `@langchain/core@1.2.18`, `pg@8.23.1`. Peer dep is only `@langchain/core ^1.0.0`. |
| 2 | `initialize` with custom table/columns/cosine/1536 | PASS | Creates the table only. No vector index. `createHnswIndex` works at 1536 dims. |
| 3a | `addDocuments` with explicit ids | PASS | Works. |
| 3b | Idempotent re-add of same ids | FAIL | Plain `INSERT`, no `ON CONFLICT`. Second add throws a unique violation. |
| 3c | Delete by ids / by filter | PASS | `delete({ ids })` and `delete({ filter })` both exist and work. `delete({ filter: {} })` deletes every row. |
| 4 | Filters (eq, in, notIn, arrayContains, AND, empty) | PARTLY | All correct, but `arrayContains` is ANY semantics, `in: []` is a SQL syntax error, and everything is compared as text. |
| 5 | similaritySearch / WithScore / retriever / MMR | PASS | Score is cosine DISTANCE (lower is better). MMR works. |
| 6a | Coexistence with generated tsvector + GIN column | PASS | Inserts and similarity search unaffected. |
| 6b | Hybrid RRF SQL via `pg` | PASS | Keyword-only "Neapolitan" found with a useless vector. About 1 ms on 6 rows, 11 ms median on 3,000 rows. |
| 7 | 3,000 chunks x 800 chars, 20 filtered searches | PASS | 1.29 s insert (batches of 100). Medians 1.4 to 5 ms, same with and without HNSW. See the HNSW post-filter caveat. |
| 8 | Surprises or blockers | PARTLY | None blocking. Several workarounds needed, listed below. |
| 9 | Python hybrid support | Confirmed from docs/source | `HybridSearchConfig` on `PGVectorStore`. JS has no equivalent. |

## 1. Install

```
npm init -y && npm pkg set type=module
npm i @langchain/pgvector @langchain/core pg
```

Installed: `@langchain/pgvector@0.1.0`, `@langchain/core@1.2.18` (zod 4.6.7, langsmith 0.11.0), `pg@8.23.1`. `npm view @langchain/pgvector peerDependencies` gives `{ '@langchain/core': '^1.0.0' }`. `pg` is a regular dependency of the package (deduped with ours), not a peer. npm reported no peer conflicts and no vulnerabilities. The package ships ESM and CJS (`dist/index.js`, `dist/index.cjs`). `import { PGVectorStore } from "@langchain/pgvector"` works in a Node 24 ESM script. `@langchain/core` has to be v1.x. Older v0.3 projects would clash.

## 2. initialize and DDL

```js
const store = await PGVectorStore.initialize(new FakeEmb(), {
  postgresConnectionOptions: { host, port: 54329, user, password, database },
  tableName: "chunks",
  columns: { idColumnName: "id", vectorColumnName: "embedding",
             contentColumnName: "content", metadataColumnName: "metadata" },
  distanceStrategy: "cosine",
  dimensions: 1536,
});
```

Result: PASS. Observed DDL (from the source, confirmed with `\d` and `information_schema`):

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS "chunks" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  "content" text, "metadata" jsonb, "embedding" vector(1536));
```

- No vector index is created. Only `chunks_pkey` exists after `initialize`.
- Without `dimensions`, the column is an untyped `vector`, which cannot be HNSW-indexed. Always pass `dimensions`.
- `initialize` always runs `CREATE EXTENSION IF NOT EXISTS` and `CREATE TABLE IF NOT EXISTS`. It needs the right to create the extension unless the table already exists. There is a `skipInitializationCheck` option in the source (not tested).
- `await store.createHnswIndex({ dimensions: 1536 })` gives `CREATE INDEX embedding_embedding_hnsw_idx ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')`. It takes 2.7 s on 3,000 rows.
- `createHnswIndex` swallows errors (`console.error` and no throw). Check `pg_indexes` yourself. The index name is not table-specific unless you pass `namespace`.
- The code builds the index on `(embedding::vector(1536))`. Postgres strips the redundant cast for a `vector(1536)` column, so the index is a normal one. `EXPLAIN` confirmed it is used (see section 7).

## 3. addDocuments, idempotency, delete

```js
await store.addDocuments(docs, { ids });          // ok
await store.addDocuments(docs, { ids });          // again
```

Second call error: `Error inserting: duplicate key value violates unique constraint "chunks_pkey"` (pg code 23505). The store also `console.error`s the raw pg error. The insert is `INSERT INTO ... VALUES ...` with no `ON CONFLICT`, so it is neither upsert nor idempotent. Count stays at 5. The error is thrown for the whole 500-row internal chunk, so earlier chunks of a large call are already committed and there is no transaction around the whole call.

Ids must be valid uuids because the column is uuid. Without `ids`, Postgres generates them (`gen_random_uuid()`) and `addDocuments` does not return them.

Delete:
- `store.delete({ ids: [...] })` works.
- `store.delete({ filter: { document_id: "14" } })` works. A number filter also matches a number-stored value (`{ document_id: 16 }`).
- `delete({})` throws `You must specify either ids or a filter when deleting documents.` Both ids and filter throws too.
- DANGER: `delete({ filter: {} })` is accepted and deletes ALL rows (count went 2 to 0). Guard this in our wrapper.
- Filter delete uses the same filter builder as search, so it is `metadata ->> key = value`, not jsonb containment (the docstring says containment, the code does not).

Workaround for idempotent ingest: `delete({ filter: { document_id } })` followed by `addDocuments` for that document, ideally in one transaction through our own `pg` client. Or write our own `INSERT ... ON CONFLICT (id) DO UPDATE` via `pg` and use the store only for reads. `addVectors` is public, so pre-computed embeddings can be inserted through the store, but it has the same insert statement.

## 4. Filters (`t4.mjs`)

Seed: 5 docs. `document_id` stored as string "12".."15" and as number 16 for the cello. Query "double reed woodwind instrument", k = 10.

| Filter | Result |
|---|---|
| `{ source_type: "wiki" }` | PASS (Tuba) |
| `{ document_id: "12" }` (string stored) | PASS |
| `{ document_id: 12 }` (number vs string stored) | PASS |
| `{ document_id: "16" }` (string vs number stored) | PASS |
| `{ document_id: 16 }` (number stored) | PASS |
| `{ source_type: { in: ["wiki","textbook"] } }` | PASS |
| `{ document_id: { in: [12, 16] } }` (mixed storage) | PASS |
| `{ source_type: { notIn: ["encyclopedia"] } }` | PASS |
| `{ topics: { arrayContains: ["woodwinds"] } }` | PASS (Cor anglais, Oboe) |
| `{ topics: { arrayContains: ["woodwinds","brass"] } }` | PASS under ANY semantics: returned all 3 docs with either topic |
| `{ topics: { arrayContains: ["woodwinds","instruments"] } }` | returns 4 docs, not just the one with both. ANY semantics, not ALL. It is a jsonb `?|` operator. |
| `{ source_type: "encyclopedia", topics: { arrayContains: ["instruments"] } }` (AND) | PASS (Cor anglais, Cello) |
| `{ source_type: { in: [...] }, document_id: "13" }` (AND) | PASS |
| `{ source_type: "nope" }` | PASS, empty array |
| `{ source_type: { neq: "encyclopedia" } }` | PASS |
| `{ revision_id: { gte: 104 } }` | PASS (cast to numeric) |
| `{ aliases: "English horn" }` (equality against an array key) | returns [] (`->>` yields the JSON text) |
| `{ source_type: { in: [] } }` | FAIL: `syntax error at or near ")"` (generates `IN ()`) |
| `{ license: null }` | returns [] (`->> = NULL` is never true; no IS NULL support) |

Filter quirks:
- All equality and `in`/`notIn` compare `metadata ->> key` (text) with the parameter. Numbers work only because `pg` sends the parameter as text. Number 12 matches string "12" and vice versa. Fine for `document_id`, but it prevents a btree/GIN-friendly jsonb `@>` match.
- No OR, no nested boolean logic, and no ALL-of for arrays. Multiple keys are always AND.
- `notIn` and `in` skip rows where the key is missing (NULL), whereas `neq` includes them.
- The filter type is just a plain object. Passing an unsupported operator is silently ignored (the operator loop just does nothing), which would make a search unfiltered. Validate filters in our code.
- The filter always uses `->>`, so it is a sequential filter on a jsonb column. Without a functional index on `(metadata ->> 'source_type')` it is a scan (cheap at our scale).

## 5. Search API

```js
await store.similaritySearch(q, 10, filter)
await store.similaritySearchWithScore(q, 5)
store.asRetriever({ k: 2, filter: { source_type: "encyclopedia" } }).invoke(q)
store.asRetriever({ k: 2, searchType: "mmr", searchKwargs: { fetchK: 5, lambda: 0.5 }, filter }).invoke(q)
await store.maxMarginalRelevanceSearch(q, { k: 3, fetchK: 5, lambda: 0.5 })
```

All PASS.
- Score is the raw cosine distance (`embedding <=> $1`), ascending: `Oboe 0.46, Cor anglais 0.62, Cello 0.84, Tuba 0.89, Sonata form 1.02`. A self-query gives 0. Despite the name "score", lower is better and the range is 0 to 2. Convert with `1 - distance` if a similarity is needed.
- Returned `Document.id` is the row uuid, and `metadata` is the jsonb as stored (url, title, aliases, ...). Retriever `k` and `filter` are honoured.
- MMR works through the retriever and directly. It fetches `fetchK` rows with embeddings and removes the embedding from the metadata. The first run returned `["Oboe","Cor anglais"]` for the retriever.
- A wrong-dimension insert fails with `Error inserting: expected 1536 dimensions, not 3`.

## 6. Coexistence and hybrid SQL (`t6.mjs`)

```sql
ALTER TABLE chunks ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
```

PASS. Later `addDocuments` (with and without ids), `similaritySearch` with filter and MMR all still work. The store's `INSERT` lists explicit columns, so generated extra columns are fine, and `SELECT *` just returns an unused `tsv` field. (One thing to watch: `searchPostgres` does `SELECT *`, so it also pulls the tsvector and the embedding over the wire on every search. The cost is minor at k = 4 but real.)

Hybrid query (pg client, RRF k = 60, filter on source_type):

```sql
WITH v AS (
  SELECT id, row_number() OVER (ORDER BY embedding <=> $1::vector) AS r
  FROM chunks WHERE metadata->>'source_type' = ANY($3::text[])
  ORDER BY embedding <=> $1::vector LIMIT 50),
t AS (
  SELECT id, row_number() OVER (ORDER BY ts_rank_cd(tsv, q) DESC) AS r
  FROM chunks, websearch_to_tsquery('english', $2) q
  WHERE tsv @@ q AND metadata->>'source_type' = ANY($3::text[])
  ORDER BY ts_rank_cd(tsv, q) DESC LIMIT 50)
SELECT c.id, c.metadata->>'title' AS title,
  COALESCE(1.0/(60+v.r),0) + COALESCE(1.0/(60+t.r),0) AS rrf
FROM v FULL OUTER JOIN t USING (id) JOIN chunks c USING (id)
ORDER BY rrf DESC LIMIT 5
```

Results:
- Query "Neapolitan" with a vector from unrelated text (useless): the three docs that contain the word (Tuba, Cor anglais, Sonata form) ranked first via the text rank, then vector-only docs with lower RRF. PASS.
- Same with `source_type = ['textbook']`: only Sonata form. PASS.
- "double reed woodwind": Cor anglais and Oboe on top, tied at 0.03252 (both ranks 1 and 2). Sensible.
- Timing: 0.7 to 1.8 ms on 6 rows. After loading 3,000 more rows (HNSW present): median 11.0 ms over 20 runs (client round trip on localhost, vector literal included). The planner ran sequential scans at this size.

## 7. Scale (`t7.mjs`)

- 3,000 synthetic chunks (800 chars each, metadata like the planned schema), `addDocuments` called with 100 docs per call (store internal chunk size 500, so one INSERT per call). Total 1.29 s including fake embedding. Store `chunkSize` config exists (default 500). A single 500-row INSERT with 1536-dim vectors as text parameters is fine. Postgres limit is 65,535 bind params, and 500 x 4 = 2,000, so OK.
- `createHnswIndex` on 3,000 rows: 2.70 s.
- 20 `similaritySearch` calls with filter (fake embedding time included, around 0.3 ms):

| Filter | No index (median) | HNSW (median) |
|---|---|---|
| `source_type` eq (about 750 rows match) | 4.6 ms | 5.2 ms |
| `in` + `arrayContains` | 2.4 ms | 2.7 ms |
| `document_id` eq (10 rows match) | 1.4 ms | 2.1 ms |

With HNSW present the planner still chose a sequential scan (`EXPLAIN`: Seq Scan plus Sort, cost 838). That is why timings are equal. With `SET enable_seqscan=off` the planner uses `Index Scan using embedding_embedding_hnsw_idx` for both unfiltered and filtered queries, so the index is compatible with the store's query. These timings therefore do not show a benefit from HNSW. At 3,000 rows exact search is fast enough that it does not matter.

HNSW post-filter caveat (confirmed, forced index scan, pgvector 0.8.7, default `hnsw.ef_search` = 40):
- `document_id = '105'` (10 of 3,006 rows), `LIMIT 10`: returned 0 rows.
- `source_type = 'wiki'` (about 25% of rows), `LIMIT 10`: returned 8 rows.
- With `SET hnsw.iterative_scan = relaxed_order`: the document_id query returned 10.

So once the table is large enough that the planner picks the index, selective metadata filters can silently return fewer (or zero) results. The store has no hook to set session GUCs per query. Options: set `hnsw.iterative_scan` in the pool's connection options (`options: "-c hnsw.iterative_scan=relaxed_order"` through `postgresConnectionOptions`, not tested via the store), raise `hnsw.ef_search`, or skip the HNSW index until the table is large.

## 8. Other surprises and blockers

- The store requires the exact column layout (id uuid, content text, metadata jsonb, embedding vector) and owns table creation by default, but it works fine against a table we create ourselves (extra columns allowed). Column names are configurable. Table and column names are interpolated into SQL strings (not parameterised), so use trusted constants only.
- Dimension limit: the HNSW doc string says up to 2000 dims. 1536 works.
- No upsert, no update API, no transaction control, no ability to run multiple writes atomically.
- Errors are `console.error`-ed and rethrown wrapped as `Error inserting: <pg message>`, so the original pg error code is lost in the thrown error (only in the console log).
- `similaritySearch` uses `SELECT *`, so it fetches the embedding and tsv columns for every hit.
- `Document.id` is populated on results (nice for citations).
- Retriever `filter` is a plain object only, and there is no way to inject a SQL fragment or an OR.
- The optional `collectionTableName` / collections mode (multi-tenancy) adds a second table. We did not use it.
- Not tested: concurrent writers, the `skipInitializationCheck` option, `extensionSchemaName`, `distanceStrategy` other than cosine, TypeScript typings, behaviour with a real `pg.Pool` instance passed in (`pool` config), `ensureTableInDatabase` against a pre-existing table with a different layout.

## 9. Python comparison (read, not run)

`langchain-postgres` v2 has hybrid search in its `PGVectorStore` (async engine API: `PGEngine`, `PGVectorStore.create_sync`) via `HybridSearchConfig`, passed as `hybrid_search_config`. From the repo source (`langchain_postgres/v2/hybrid_search_config.py`) the fields are `tsv_column`, `tsv_lang` (default `pg_catalog.english`), `fts_query`, `fusion_function` (default `weighted_sum_ranking`), `fusion_function_parameters`, `primary_top_k`, `secondary_top_k`, `index_name` (`langchain_tsv_index`), `index_type` (`GIN`). `reciprocal_rank_fusion(primary_search_results, secondary_search_results, rrf_k=60, fetch_top_k=4, **kwargs)` is provided. The README example is `HybridSearchConfig(fusion_function=reciprocal_rank_fusion)` and a plain `similarity_search(...)` then returns hybrid results. The README says the Google Cloud SQL and AlloyDB integrations do not support hybrid search.

Sources:
- https://github.com/langchain-ai/langchain-postgres (README section "Hybrid Search with PGVectorStore")
- https://raw.githubusercontent.com/langchain-ai/langchain-postgres/main/langchain_postgres/v2/hybrid_search_config.py
- Example notebook (URL inferred, not opened): https://github.com/langchain-ai/langchain-postgres/blob/main/examples/pg_vectorstore_how_to.ipynb

I did not install or run it, and I did not read the notebook, so I cannot confirm how the tsv column is created (by the engine or by us), how filters interact with hybrid mode, or its performance. The summaries above came from a web-fetch summariser, not from reading the full source myself.

## Recommendation

PGVectorStore 0.1.x is good enough as the storage and plain-vector retrieval layer for this project, provided we treat it as a thin wrapper and do not rely on it for ingest or hybrid search.

Workarounds needed:
1. Own the DDL. Create the chunks table, tsv column, GIN index and the HNSW index ourselves in a migration (with a `vector(1536)` column and a functional index on `metadata->>'source_type'` if needed). Pass `dimensions` anyway, or use `skipInitializationCheck`.
2. Idempotent ingest: delete by `document_id` filter and re-add inside one transaction, or write our own `INSERT ... ON CONFLICT` through `pg`. Do not call `addDocuments` twice with the same ids. Ids must be uuids.
3. Hybrid search: write the RRF SQL ourselves (section 6) in a small repository module with the `pg` pool. It is about 20 lines and ran in about 11 ms at 3,000 rows. Keep PGVectorStore for the dense path and MMR.
4. Guard filters: reject empty filters on `delete`, drop empty `in` arrays, validate operator names (unknown ones are silently ignored), and remember that `arrayContains` means ANY and equality compares text.
5. Large table: configure `hnsw.iterative_scan` (and a higher `ef_search`) on the connection, because selective filters with HNSW returned 0 rows in our test. Re-test with real data volumes before turning HNSW on. At a few thousand chunks exact scan is fast enough.
6. Convert distance to similarity (`1 - distance`) before showing scores.

What would justify switching the backend to Python (`langchain-postgres` v2): wanting the library to own hybrid search (`HybridSearchConfig`, RRF built in) rather than our own SQL, or wanting a richer, maintained, async engine API (index management, upsert-like flows) and a larger ecosystem for the rest of the RAG pipeline (rerankers, evaluation). That would need to be checked first by actually running it, which this spike did not do. On the evidence here, a hand-written hybrid query is small and fast enough that it does not justify a language switch on its own. Switch if we find ourselves rebuilding more than the hybrid query and the ingest upsert (for example filters with OR, per-query GUCs, or transactional multi-row writes).
