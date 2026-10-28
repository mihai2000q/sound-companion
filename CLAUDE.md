# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Sound Companion is a RAG chatbot that teaches music theory and instruments from a curated, cited corpus plus local calculation tools. Stories 1 (scaffold), 2 (Seed list and ingestion) and 3 (chunking, embeddings, indexing) are done, and story 4 (baseline retrieval, golden set, retrieval metrics) is next. Work proceeds story by story from `docs/IMPLEMENTATION-PLAN.md` (each story lists acceptance criteria and facts to verify first). There is no lint tooling yet, and tests are written only for the AI parts of the bot.

## Commands

Run from the repo root unless noted. Settings come from the root `.env` (copy `.env.example`).

- `docker compose up --build`: Postgres, the server (applies migrations on startup) and the client dev server.
- `cd sound-companion.server && uv run python -m app.db.migrate`: apply migrations by hand. `uv run alembic revision --autogenerate -m "name"` creates one from a change to `app/db/models.py`, `uv run alembic check` finds drift.
- `cd sound-companion.server && uv run python -m scripts.ingest`: Wikipedia fetch (cached), Open Music Theory clone, clean, floor, report, store. `--dry-run` stores nothing, `--limit N` takes the first N Wikipedia entries and stores nothing. The first run makes about 160 requests at 1 per second, later runs make none.
- `cd sound-companion.server && uv run python -m scripts.chunk`: split the stored documents into chunks and print the count, size spread and a sample (`--sample "Title"`), no model calls. `uv run pytest` runs the tests. `scripts.eval_retrieval [--label L] [--mode vector|hybrid] [--filters ...]` prints (and saves to `eval/results/`) precision@5 and recall@5 on the golden set (query embeddings only), `scripts.eval_tools [--label L] [--model ID]` scores tool calls on `data/golden-tools.json` (agent calls only, searches stubbed, about 72k tokens), `scripts.eval_injection [--label L] [--repeats N]` runs `data/injection-tests.json` (agent cases on the chat model, searches answered by planted chunks, exits 1 on a failure), `scripts.compare_runs A B` compares two saved runs of any kind. `scripts.export_run [--only q01,q02] [--mode ...]` runs the `answer` questions of the golden set through the real agent and saves answers, retrieved chunks and tool results to `data/runs/<timestamp>.json` for RAGAs (real model calls, written to `usage_log`). `uv sync --group ragas && uv run --group ragas python -m eval.run_ragas data/runs/<file>.json [--only ...] [--tool-contexts]` scores an export with RAGAs (judge model `OPENROUTER_JUDGE_MODEL`, spend written to `usage_log` as `eval`). Plain `uv run` may drop the `ragas` group again.
- `cd sound-companion.server && uv run python -m scripts.setup_chunks`: create the `chunks` table and its HNSW index (safe to repeat). `scripts.index` chunks, embeds (about 0.02 credits for the whole Corpus, 3 to 4 minutes), upserts and deletes stale chunks (`--limit N --title "T"` restricts it), `scripts.scan_injection [--dry-run]` reports instruction-like strings in chunks and writes `injection_flag` rows, `scripts.search "query"` searches through the `Retriever` (`--topic`, `--title`, `--source-type`, `--demo`).

`RETRIEVER_MODE=vector|hybrid` (default `vector`, an unknown value stops startup) picks the retriever for `POST /api/chat` and the default of `eval_retrieval --mode`. The golden set has 22 retrieval questions since issue #88 (q18 to q25 are exact-term and Alias queries), so compare against `vector-baseline-25q`, not `vector-baseline`.

Stack: React + Vite + TypeScript + Tailwind/DaisyUI (`sound-companion.client/`), Python 3.12 + FastAPI + LangChain `create_agent` (`sound-companion.server/`), PostgreSQL + pgvector in Docker, OpenRouter for the LLM and embeddings. Secrets (OpenRouter key) live in `.env`, never committed.

## Where to look

- `CONTEXT.md`: domain language (Note, Pitch class, Sounding pitch, Convention, Citation, ...). Use these terms, and avoid the synonyms it lists.
- `docs/GLOSSARY.md`: technical terms (RAG, RRF, SSE).
- `docs/DECISIONS.md`: numbered decision log with reasons and "revisit if". Check it before reopening a choice, and add an entry when making one.
- `docs/ARCHITECTURE.md`: components, request flow, SSE event table, cost guard, folder layout.
- `docs/DOMAIN.md`, `DATABASE-SCHEMA.md`, `EVALUATION.md`, `SECURITY.md`: corpus and bot behaviour, tables and hybrid query, golden set and RAGAs, threat model.
- `docs/research/`: verified facts about data sources, libraries and APIs. Prefer these over memory when a library behaviour matters.
- `docs/archive/`: superseded designs (metal artists; SvelteKit/TypeScript). Do not follow them.

## Architecture (big picture)

One streaming endpoint, `POST /api/chat` (body: `thread_id` + `message`), returns an SSE stream of typed events (`token`, `tool_call`, `tool_result`, `citations`, `queries`, `progress`, `usage`, `error`, `done`). The browser reads it with `fetch` plus a stream reader, not `EventSource`. The same events feed logging, so UI and monitoring cannot disagree.

The backend runs a LangChain `create_agent` with no router. Retrieval is a tool (`search_knowledge_base`) that does multi-query rewrite with a cheap model, then retrieves, merges and wraps chunks as data (prompt-injection defence). Decomposition happens through the agent's tool loop. Music tools: `chord_info` (pychord), `scale_info` and `interval_between` (music21), `transpose_for_instrument` (hand-written offset table + music21 spelling), `note_frequency` (hand-written). Memory is per `thread_id` via `AsyncPostgresSaver`.

Retrieval sits behind a small `Retriever` interface: baseline is `langchain-postgres` `PGVectorStore` (v2); hybrid search (vector + `ts_rank`, fused with RRF) is our own SQL via psycopg. Ingestion is an idempotent script, not part of the request path: `scripts.ingest` caches pages and stores cleaned `documents`, `scripts.index` chunks them with deterministic uuid5 chunk ids (upsert, then delete stale chunks) and embeds them into the `chunks` table (made by the library helper, not Alembic). Our own tables are SQLAlchemy models migrated with Alembic (`app/db/models.py`, `app/db/migrations/`); the hybrid query stays hand-written SQL.

## Constraints that are easy to miss

- Pin `langchain-postgres` to an exact version (0.0.x; its `HybridSearchConfig` has a state-mutation bug, so it is comparison-only).
- HNSW needs a custom `QueryOptions` setting `hnsw.iterative_scan = relaxed_order`, or selective filters return 0 rows.
- `music21` spells flats as `-`; normalise to `b`. Both music libraries raise on invalid input, so tools must return structured errors.
- Tool results state their Convention (scientific pitch notation, C4 = middle C); when a retrieved Citation uses another Convention, show both.
- Budget: target under 1 credit of OpenRouter spend, soft warning at 1, backend refuses requests at 4. Every model call is written to `usage_log`.
- Wikipedia ingestion: REST HTML endpoint, about 1 request per second, descriptive User-Agent. Corpus is CC BY-SA, so store `revision_id`, `license` and `url` per document and show attribution.
- Out of scope: authentication, multi-language, audio input, YouTube links, remote or own MCP servers, public deployment.

## Agent skills

### Issue tracker

GitHub Issues via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five roles, plus type labels (feature, bug, refactor) and area labels (client, server). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context. Domain language in `CONTEXT.md`, technical terms in `docs/GLOSSARY.md`, decisions in `docs/DECISIONS.md`. See `docs/agents/domain.md`.
