# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Sound Companion is a RAG chatbot that teaches music theory and instruments from a curated, cited corpus plus local calculation tools. The repo is in the **documentation phase**: there is no code, build, lint or test tooling yet. Work proceeds story by story from `docs/IMPLEMENTATION-PLAN.md` (each story lists acceptance criteria and facts to verify first). Commands will be added here once story 1 (scaffold) lands.

Planned stack: React + Vite + TypeScript + Tailwind/DaisyUI (`frontend/`), Python 3.12 + FastAPI + LangChain `create_agent` (`backend/`), PostgreSQL + pgvector in Docker, OpenRouter for the LLM and embeddings. Secrets (OpenRouter key) live in `.env`, never committed.

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

Retrieval sits behind a small `Retriever` interface: baseline is `langchain-postgres` `PGVectorStore` (v2); hybrid search (vector + `ts_rank`, fused with RRF) is our own SQL via psycopg. Ingestion is an idempotent script (deterministic uuid5 chunk ids, upsert then delete stale chunks), not part of the request path.

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
