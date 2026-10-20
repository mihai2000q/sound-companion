# Database schema

PostgreSQL with the `pgvector` extension, one container, one database. Docker Hub has `pgvector/pgvector` tags pg13 to pg18 (per the research), so `pg16` is valid but not the newest. Pick one at setup.

Chunks live in the table layout that `@langchain/pgvector`'s `PGVectorStore` expects, so core retrieval needs no custom code (the course pattern: add documents, then use a retriever). Per the research, the store creates and uses `id uuid`, a content column, `metadata jsonb` and a vector column, and inserts only those. Verify column names and the `columns` option when implementing story 3.

## Knowledge base

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Bookkeeping and attribution, one row per Corpus document
CREATE TABLE documents (
  id            BIGSERIAL PRIMARY KEY,
  title         TEXT NOT NULL,
  source_type   TEXT NOT NULL CHECK (source_type IN ('encyclopedia','textbook')),
  topics        TEXT[] NOT NULL DEFAULT '{}',
  aliases       TEXT[] NOT NULL DEFAULT '{}',
  url           TEXT NOT NULL UNIQUE,
  license       TEXT NOT NULL,                 -- 'CC BY-SA 4.0'
  revision_id   TEXT,                          -- Wikipedia revision id or git commit
  fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  char_count    INTEGER NOT NULL
);

-- Chunks, in the layout PGVectorStore expects
CREATE TABLE chunks (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content    TEXT NOT NULL,                    -- starts with a title line "Cor anglais (also: English horn)"
  metadata   JSONB NOT NULL DEFAULT '{}',      -- document_id, title, aliases, source_type, topics, section, url, license, revision_id
  embedding  VECTOR(1536)                      -- text-embedding-3-small, set when the model is chosen
);

CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_metadata_idx  ON chunks USING gin (metadata);
```

Notes:

- The embedding dimension is 1536 for `openai/text-embedding-3-small`. HNSW supports at most 2000 dimensions on the `vector` type (per the `@langchain/pgvector` docs the research read), so do not switch to a 3072-dimension model without requesting reduced `dimensions`.
- `document_id` lives inside `metadata` because `PGVectorStore` never writes a separate column. Deleting a document means deleting chunks by `metadata->>'document_id'`, done in one transaction with the `documents` row.
- The title line (with Aliases) at the top of each chunk makes alias searches work in both vector and keyword search.
- Filters: `PGVectorStore` supports equality, `in`, `notIn`, `arrayContains`, `gt`, `gte`, `lt`, `lte` and `neq` (no `or` or `not`). Equality compares as text. `topics` filters use `arrayContains`.
- Spike findings ([research/pgvectorstore-spike.md](research/pgvectorstore-spike.md), run with fake embeddings on 3,000 chunks): the store creates the table but no vector index, so our migration owns the DDL and the HNSW index. `addDocuments` is a plain INSERT, so re-adding an id throws. `arrayContains` means "any of", `in: []` is a SQL error, an unknown operator is silently ignored (the search runs unfiltered), and `delete({ filter: {} })` deletes every row. Wrap filters in our own validation (see [SECURITY.md](SECURITY.md)).
- HNSW with a selective filter returned too few rows in the spike (0 of 10 for a filter matching 10 of 3,006 rows when the index was forced). `SET hnsw.iterative_scan = relaxed_order` fixed it in a direct SQL test, not yet through the store. Postgres chose a sequential scan at 3,000 rows anyway, so test with the real corpus before relying on the index.

## Hybrid search (story 15 only)

Add a generated keyword column. The store never writes it, so it does not clash:

```sql
ALTER TABLE chunks
  ADD COLUMN tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
```

Hybrid query (custom retriever, reciprocal rank fusion, 60 is the usual constant):

```sql
WITH vec AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $1) AS r
  FROM chunks
  WHERE ($3::text IS NULL OR metadata->>'source_type' = $3)
  ORDER BY embedding <=> $1
  LIMIT 20
), kw AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank(tsv, q) DESC) AS r
  FROM chunks, websearch_to_tsquery('english', $2) q
  WHERE tsv @@ q
    AND ($3::text IS NULL OR metadata->>'source_type' = $3)
  ORDER BY ts_rank(tsv, q) DESC
  LIMIT 20
)
SELECT c.id, c.content, c.metadata,
       COALESCE(1.0/(60+vec.r), 0) + COALESCE(1.0/(60+kw.r), 0) AS score
FROM chunks c
LEFT JOIN vec ON vec.id = c.id
LEFT JOIN kw  ON kw.id = c.id
WHERE vec.id IS NOT NULL OR kw.id IS NOT NULL
ORDER BY score DESC
LIMIT $4;
```

Per the research, `@langchain/pgvector` 0.1.0 has no hybrid search, and `BM25Retriever` lives in the deprecated `@langchain/community` and works in memory, so this SQL is the main hybrid path, wrapped in a `BaseRetriever` subclass. `EnsembleRetriever` is in `@langchain/classic`, if we ever need it.

## Instrument data

The transposition table is a code constant in `src/lib/server/tools/instruments.ts` (about 14 rows, each with a Wikipedia URL as its Citation), not a database table. It is small, reviewed by hand, and unit-tested.

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

OpenRouter returns `usage.cost` on every response (on the last chunk when streaming), in credits. Credits are treated as USD for the caps (verify on the account page, the research could not confirm it from the docs).

## Conversation memory

`PostgresSaver` (`PostgresSaver.fromConnString(...)` then `await setup()`) creates and manages its own tables: `checkpoint_migrations`, `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`. Do not hand-write or read them directly. Messages for the sidebar and JSON export come from `agent.getState({ configurable: { thread_id } }).values.messages`, plus the `threads` table for titles. Per the research this works with the JS API (it was run with `MemorySaver`, and `PostgresSaver` was read from source, so test it against the database in story 5).

## Evaluation data

Golden set and exported runs are files, not tables: `data/golden-set.json` and `data/runs/*.json`. See [EVALUATION.md](EVALUATION.md).

## Migrations

Plain numbered SQL files in `src/lib/server/db/migrations/`, applied by a small script on startup. No ORM.
