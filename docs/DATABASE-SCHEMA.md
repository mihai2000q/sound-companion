# Database schema

PostgreSQL with the `pgvector` extension, one container, one database. Docker Hub has `pgvector/pgvector` tags pg13 to pg18 (per the research), so `pg16` is valid but not the newest. Pick one at setup.

Chunks live in a table created by `langchain-postgres`' own helper (`PGEngine.init_vectorstore_table`), with real metadata columns, so core retrieval needs no custom code (the course pattern: add documents, then use a retriever). Everything below was exercised in [research/python-stack-spike.md](research/python-stack-spike.md) with fake embeddings and 3,000 chunks. Not tested: real embeddings, concurrent writers, very large tables.

## Knowledge base

```sql
CREATE EXTENSION IF NOT EXISTS vector;   -- the helper also runs this

-- Bookkeeping and attribution, one row per Corpus document (our own migration)
CREATE TABLE documents (
  id            BIGSERIAL PRIMARY KEY,
  title         TEXT NOT NULL,
  source_type   TEXT NOT NULL CHECK (source_type IN ('encyclopedia','textbook')),
  topics        TEXT NOT NULL DEFAULT '',        -- pipe-delimited, see below
  aliases       TEXT[] NOT NULL DEFAULT '{}',
  url           TEXT NOT NULL UNIQUE,
  license       TEXT NOT NULL,                   -- 'CC BY-SA 4.0'
  revision_id   TEXT NOT NULL,                   -- Wikipedia revision id or git commit
  sections      JSONB NOT NULL,                  -- cleaned text: [{"heading_path": [...], "text": "..."}]
  fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  char_count    INTEGER NOT NULL
);
```

The chunk table is created from Python:

```python
engine = PGEngine.from_connection_string("postgresql+psycopg://...")
engine.init_vectorstore_table("chunks", 1536, metadata_columns=[
    Column("document_id", "TEXT"), Column("title", "TEXT"), Column("aliases", "TEXT"),
    Column("source_type", "TEXT"), Column("topics", "TEXT"), Column("section", "TEXT"),
    Column("url", "TEXT"), Column("license", "TEXT"), Column("revision_id", "TEXT"),
])
store = PGVectorStore.create_sync(engine, embeddings, "chunks", metadata_columns=[...same names...])
```

Resulting table (per the spike): `langchain_id uuid` primary key, `content text`, `embedding vector(1536)`, one real column per metadata field above, and a leftover `langchain_metadata json` column for undeclared keys. The metadata column names must be declared in both places, so keep one constant list. The first chunk line is the title line with Aliases, for example `Cor anglais (also: English horn)`.

Notes:

- **Real columns** keep types, filter with typed comparisons, and index with plain btree. Do not store metadata only in the JSON column.
- **`topics` is a pipe-delimited TEXT** (`|woodwinds|instruments|`), because the library cannot filter array columns. Filter with `$like`: contains one topic `{"topics": {"$like": "%|woodwinds|%"}}`, any of with `$or`, all of with `$and`. `aliases` is only stored for display, as a delimited string, because only the title line needs searching.
- **Filters** support `$and`, `$or`, `$not`, `$in`, `$nin`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$between`, `$like` and `$exists`. Values are bound parameters, an unknown operator raises a clear `ValueError`, and an empty `$in` returns nothing. Filter values must match the column type (an int against a text column raises an error).
- **Upsert:** `add_documents(docs, ids=...)` upserts on `langchain_id` (`ON CONFLICT DO UPDATE`). Use deterministic UUIDs (uuid5 over document id, section and chunk index) so re-ingestion is idempotent.
- **Delete:** `delete(ids=...)` and `delete(filter=...)` work. An empty filter deletes nothing (the library checks), unlike the JavaScript store.
- **Scores** are cosine distance, lower is better. Convert with `1 - distance` for display.
- **Dimensions:** 1536 for `openai/text-embedding-3-small`. HNSW supports at most 2000 dimensions on the `vector` type, so do not use a 3072-dimension model without requesting reduced dimensions.
- **Insert speed:** 3,000 chunks took 7 to 11 seconds in the spike (one INSERT and commit per row, no transaction around the batch). Fine for this corpus.

### Vector index

```python
store.apply_vector_index(HNSWIndex(m=16, ef_construction=64))   # 3.0 s on 3,000 rows in the spike
```

With the index forced, a selective filter returned 0 of 10 rows (a filter matching 10 of 3,000 chunks). Setting `hnsw.iterative_scan = relaxed_order` fixed it. The library's `HNSWQueryOptions` only sets `ef_search`, so we pass a small `QueryOptions` subclass through `index_query_options` whose `to_parameter()` returns `hnsw.ef_search`, `hnsw.iterative_scan = relaxed_order` and `hnsw.max_scan_tuples` settings. At 3,000 rows Postgres uses a sequential scan anyway, so re-test with the real corpus before relying on the index. Not verified: that `SET LOCAL` always lands on the query's connection in every pool configuration.

## Hybrid search (story 15)

Add a generated keyword column and index in our own migration. The library's plain store never writes it (not yet tested together in Python, the JavaScript spike confirmed the same pattern works):

```sql
ALTER TABLE chunks
  ADD COLUMN content_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX chunks_tsv_idx ON chunks USING gin (content_tsv);
```

Hybrid query, run through psycopg (reciprocal rank fusion, 60 is the usual constant):

```sql
WITH vec AS (
  SELECT langchain_id AS id, ROW_NUMBER() OVER (ORDER BY embedding <=> %(qvec)s) AS r
  FROM chunks
  WHERE (%(source_type)s::text IS NULL OR source_type = %(source_type)s)
  ORDER BY embedding <=> %(qvec)s
  LIMIT 20
), kw AS (
  SELECT langchain_id AS id, ROW_NUMBER() OVER (ORDER BY ts_rank(content_tsv, q) DESC) AS r
  FROM chunks, websearch_to_tsquery('english', %(qtext)s) q
  WHERE content_tsv @@ q
    AND (%(source_type)s::text IS NULL OR source_type = %(source_type)s)
  ORDER BY ts_rank(content_tsv, q) DESC
  LIMIT 20
)
SELECT c.langchain_id, c.content, c.title, c.section, c.url, c.license,
       COALESCE(1.0/(60+vec.r), 0) + COALESCE(1.0/(60+kw.r), 0) AS score
FROM chunks c
LEFT JOIN vec ON vec.id = c.langchain_id
LEFT JOIN kw  ON kw.id = c.langchain_id
WHERE vec.id IS NOT NULL OR kw.id IS NOT NULL
ORDER BY score DESC
LIMIT %(k)s;
```

The query vector is passed as a pgvector value. `websearch_to_tsquery` accepts natural phrasing, unlike the library's `plainto_tsquery`, which ANDs every word. RRF is rank-only, so noise from the vector side competes with keyword hits (observed with useless fake vectors, smaller with real ones). Weights can be added later.

**Library mode (comparison only):** `HybridSearchConfig` with `tsv_column="content_tsv"` needs a table where `content_tsv` is a plain NOT NULL column that the library fills at insert, so it would need its own table. In 0.0.19 the first query's keyword text is stored on the shared config and every later query reuses it. The fix is to pass a fresh copy (with a copied `fusion_function_parameters`) as `hybrid_search_config=` on each call, plus a regression test with two different successive queries. The imports are not exported at top level: use `langchain_postgres.v2.hybrid_search_config` and `langchain_postgres.v2.indexes`.

## Instrument data

The transposition table is a code constant in `sound-companion.server/app/tools/instruments.py` (about 14 rows, each with a Wikipedia URL as its Citation), not a database table. It is small, reviewed by hand, and unit-tested.

## Usage, logs, threads

```sql
CREATE TABLE usage_log (
  id                 BIGSERIAL PRIMARY KEY,
  thread_id          TEXT NOT NULL,
  request_id         UUID NOT NULL,
  purpose            TEXT NOT NULL CHECK (purpose IN ('answer','rewrite','embed','eval')),
  model              TEXT NOT NULL,
  prompt_tokens      INTEGER NOT NULL DEFAULT 0,
  completion_tokens  INTEGER NOT NULL DEFAULT 0,
  cost_credits       NUMERIC(12,8) NOT NULL DEFAULT 0,   -- OpenRouter usage.cost, in credits
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX usage_log_thread_idx ON usage_log (thread_id);

CREATE TABLE app_logs (
  id          BIGSERIAL PRIMARY KEY,
  request_id  UUID,
  level       TEXT NOT NULL,             -- info | warn | error
  event       TEXT NOT NULL,             -- 'tool_call', 'retrieval', 'injection_flag', 'budget_block', ...
  data        JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX app_logs_event_idx ON app_logs (event, created_at);

CREATE TABLE threads (
  thread_id   TEXT PRIMARY KEY,
  title       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Total spend for the budget guard: `SELECT COALESCE(SUM(cost_credits),0) FROM usage_log;`

OpenRouter returns `usage.cost` in credits on every response (verified at HTTP level in the JavaScript research). Through `langchain-openai` it survives on non-streamed calls but is dropped on streamed ones, so the backend uses a small `ChatOpenAI` subclass (decision 46, [research](research/python-stack-spike.md), section C4). Credits are treated as USD for the caps.

## Conversation memory

`AsyncPostgresSaver` (from `langgraph-checkpoint-postgres`) creates and manages its own tables through `await saver.setup()`: `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`. Do not hand-write or read them directly. Messages for the sidebar and JSON export come from `agent.aget_state(config).values["messages"]` (verified in the spike with typed human, AI and tool messages), plus the `threads` table for titles. The saver is built on a connection pool opened with `autocommit=True`, `prepare_threshold=0` and `row_factory=dict_row`, using the plain `postgresql://` URL.

## Evaluation data

Golden set and exported runs are files, not tables: `data/golden-set.json` and `data/runs/*.json`. See [EVALUATION.md](EVALUATION.md).

## Migrations

Plain numbered SQL files in `sound-companion.server/app/db/migrations/`, applied by a small script on startup. The chunk table itself is created by the library helper from a setup script, and our migrations add the keyword column and indexes. No ORM.

**How they run.** The runner is `sound-companion.server/app/db/migrate.py`. It applies the `.sql` files in filename order, each in its own transaction, and records each applied version in a `schema_migrations` table. A version that is already recorded is skipped, so running it again changes nothing. An advisory lock keeps two runners from interleaving.

- **Automatically:** the server runs it on startup, so `docker compose up` is enough. A failing migration stops the server from starting.
- **By hand, with the stack running:** `docker compose exec server python -m app.db.migrate`
- **By hand, without the server:** `docker compose run --rm --no-deps server python -m app.db.migrate` (the database must be up).
- **On the host:** `cd sound-companion.server && uv run python -m app.db.migrate`, with the database up on `localhost:7001` (`POSTGRES_HOST` and `POSTGRES_PORT` from `.env`).

The runner prints `applied: <versions>` or `nothing to apply`.

**Adding one.** Create `NNNN_short_name.sql` in `app/db/migrations/` with the next number, for example `0002_documents.sql`. Never edit a migration that has been applied, add a new one. `0001_enable_pgvector.sql` enables the `vector` extension.
