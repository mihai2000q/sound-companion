-- One row per Corpus document: attribution, provenance and the cleaned sections Story 3 chunks.
CREATE TABLE documents (
    id           BIGSERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    source_type  TEXT NOT NULL CHECK (source_type IN ('encyclopedia', 'textbook')),
    topics       TEXT NOT NULL DEFAULT '',          -- pipe-delimited, e.g. '|woodwinds|instruments|'
    aliases      TEXT[] NOT NULL DEFAULT '{}',
    url          TEXT NOT NULL UNIQUE,
    license      TEXT NOT NULL,
    revision_id  TEXT NOT NULL,                     -- Wikipedia revision id, or git commit for the textbook
    sections     JSONB NOT NULL,                    -- [{"heading_path": [...], "text": "..."}]
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    char_count   INTEGER NOT NULL
);
