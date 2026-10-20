# Database schema

PostgreSQL with the `pgvector` extension, one container, one database. Use the `pgvector/pgvector:pg16` image (as suggested by the LangChain JS docs). Verify the exact tag at setup.

Draft DDL. The `chunks` table must match what `@langchain/pgvector` expects if `PGVectorStore` creates or reads it (id, vector, content, metadata columns). Check this when implementing story 3 and adjust.

## Knowledge base

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
  id           BIGSERIAL PRIMARY KEY,
  mbid         TEXT,
  entity       TEXT NOT NULL,
  entity_type  TEXT NOT NULL CHECK (entity_type IN ('artist','genre','history')),
  subgenres    TEXT[] NOT NULL DEFAULT '{}',
  contested    BOOLEAN NOT NULL DEFAULT false,
  url          TEXT NOT NULL,
  license      TEXT,
  provenance   TEXT NOT NULL,            -- 'music-wiki' | 'wikipedia-api'
  fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (entity, url)
);

CREATE TABLE chunks (
  id           BIGSERIAL PRIMARY KEY,
  document_id  BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  section      TEXT,
  content      TEXT NOT NULL,            -- heading included in the text
  metadata     JSONB NOT NULL DEFAULT '{}',
  embedding    VECTOR(1536),             -- dimension depends on the embedding model: set at setup
  tsv          TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_idx       ON chunks USING gin (tsv);
CREATE INDEX chunks_metadata_idx  ON chunks USING gin (metadata);
CREATE INDEX documents_entity_idx ON documents (entity);
CREATE INDEX documents_subgenres_idx ON documents USING gin (subgenres);
```

The vector dimension depends on the embedding model chosen at setup (for example 1024, 1536 or 3072). Changing the model means re-embedding the corpus.

`ON DELETE CASCADE` is the transactional benefit of keeping vectors in Postgres: removing a document removes its chunks atomically.

## Hybrid query (fallback implementation)

```sql
WITH vec AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $1) AS r
  FROM chunks
  WHERE ($3::text IS NULL OR metadata->>'entity_type' = $3)
  ORDER BY embedding <=> $1
  LIMIT 20
), kw AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank(tsv, q) DESC) AS r
  FROM chunks, websearch_to_tsquery('english', $2) q
  WHERE tsv @@ q
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

Only used if the built-in `EnsembleRetriever` route is awkward. 60 is the usual RRF constant.

## Usage, logs, exports

```sql
CREATE TABLE usage_log (
  id                 BIGSERIAL PRIMARY KEY,
  thread_id          TEXT NOT NULL,
  request_id         UUID NOT NULL,
  purpose            TEXT NOT NULL CHECK (purpose IN ('answer','rewrite','embed','eval')),
  model              TEXT NOT NULL,
  prompt_tokens      INTEGER NOT NULL DEFAULT 0,
  completion_tokens  INTEGER NOT NULL DEFAULT 0,
  cost_eur           NUMERIC(10,6) NOT NULL DEFAULT 0,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX usage_log_thread_idx ON usage_log (thread_id);

CREATE TABLE app_logs (
  id          BIGSERIAL PRIMARY KEY,
  request_id  UUID,
  level       TEXT NOT NULL,             -- info | warn | error
  event       TEXT NOT NULL,             -- e.g. 'tool_call', 'retrieval', 'injection_flag', 'budget_block'
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

Total spend for the budget guard: `SELECT COALESCE(SUM(cost_eur),0) FROM usage_log;`

## Conversation memory

`PostgresSaver` (LangGraph checkpointer) creates and manages its own tables on setup. Do not hand-write them and do not read them directly for the UI. Message history shown in the sidebar and exported as JSON comes from the checkpointer's state API for a `thread_id`, plus the `threads` table for titles. Verify the exact API when implementing story 5 and story 14.

## Evaluation data

Golden set and exported runs are files, not tables: `data/golden-set.json` and `data/runs/*.json`. See [EVALUATION.md](EVALUATION.md).

## Migrations

Plain numbered SQL files in `src/lib/server/db/migrations/` applied by a small script at startup (or on `docker compose up`). No ORM.
