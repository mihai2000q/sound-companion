# Architecture

## Overview

Two projects in one repository. A React single-page app (`frontend/`) talks to a FastAPI backend (`backend/`) over one streaming endpoint. The backend owns all LangChain logic, the music tools, ingestion and evaluation. Postgres (with pgvector) holds the knowledge base, conversation memory, usage and logs.

```
Browser (React + Tailwind/DaisyUI, Vite dev server)
   |  POST /api/chat  (fetch, body: thread_id + message)      /api/* proxied by Vite to :8000
   |  <- SSE stream of typed events
FastAPI backend
   |-- input validation, rate limit, budget guard
   |-- create_agent (LangChain)
   |      |-- tool: search_knowledge_base  -> Retriever -> Postgres (pgvector, + tsvector for hybrid)
   |      |-- tool: chord_info              -> pychord
   |      |-- tool: scale_info / interval_between -> music21
   |      |-- tool: transpose_for_instrument -> instrument table (+ music21 spelling)
   |      |-- tool: note_frequency           -> hand-written maths
   |-- AsyncPostgresSaver checkpointer (memory per thread_id)
   |-- usage + log writers -> Postgres
OpenRouter  (chat model, query-rewrite model, embeddings)
Eval scripts (pytest-style CLI, RAGAs) in the same Python project
```

## Request flow

1. The UI sends the user message and `thread_id`.
2. The backend validates input (length, characters), checks the rate limit, and checks cumulative spend against the caps.
3. The agent receives the message with the system prompt (see [DOMAIN.md](DOMAIN.md#bot-behaviour)).
4. The model decides whether to call tools. For explanations it calls `search_knowledge_base`. For calculations it calls a music tool.
5. `search_knowledge_base` rewrites the query into several variants (cheap model), retrieves for each variant, merges and de-duplicates, and returns chunks wrapped as data (see [SECURITY.md](SECURITY.md)). It also emits `citations` and `queries` events through the agent's custom stream.
6. For comparisons the model may call tools several times (this is decomposition).
7. Tool results state their Convention (scientific pitch notation). If a retrieved Citation uses another Convention, the answer shows both.
8. The final answer streams as tokens, with Citations that reference retrieved chunks or tool results.
9. Token usage and cost are written to `usage_log`, and a `usage` event closes the stream.

## Query translation and structured retrieval

| Technique | Where it lives |
|---|---|
| Multi-query rewrite | Inside `search_knowledge_base`, using the cheap model |
| Decomposition | Agent loop: the model calls tools several times, guided by the system prompt |
| Structured retrieval | Typed arguments of `search_knowledge_base` (`source_type`, `topic`, `title`) turned into metadata filters (`PGVectorStore` filters support `$and`, `$or`, `$not`, `$in` and `$like`) |
| Not used | HyDE and step-back (low value for factual questions, extra cost) |

## Retrieval

Behind a small `Retriever` interface in `backend/app/rag/`:

- **Baseline (core):** `langchain-postgres` `PGVectorStore` (v2 API, `PGEngine`) with real metadata columns, used through `add_documents` and `as_retriever(search_kwargs={"k": ..., "filter": ...})`, the pattern from the course.
- **Hybrid (story 15, hard task):** our own SQL (vector similarity plus `ts_rank`, fused with reciprocal rank fusion) run through psycopg, see [DATABASE-SCHEMA.md](DATABASE-SCHEMA.md#hybrid-search-story-15). The library's `HybridSearchConfig` is a second mode for comparison only, because in `langchain-postgres` 0.0.19 it mutates the shared config and reuses the first query's keywords unless a fresh config copy is passed on every call (confirmed in the spike).
- **HNSW:** created with `apply_vector_index(HNSWIndex(...))`. A selective filter returned 0 rows with the index forced until `hnsw.iterative_scan = relaxed_order` was set through a small custom `QueryOptions` subclass, so we ship that class.

## Streaming events (SSE)

The backend returns `text/event-stream` from a FastAPI `StreamingResponse`. The browser reads it with `fetch` and a stream reader (`EventSource` only supports GET and cannot send a JSON body). Each message is `data: <json>\n\n`.

| Event `type` | Payload | UI use | Source in the agent stream |
|---|---|---|---|
| `token` | `{ text }` | Append to the answer | `messages` mode, `AIMessageChunk` with content |
| `tool_call` | `{ id, name, args }` | Show a tool card in "running" state | `updates` mode (complete call from the model node) |
| `tool_result` | `{ id, name, content, durationMs }` | Fill the tool card | `updates` mode (tools node) |
| `citations` | `{ items: [{ title, section, url, score, license }] }` | Citation chips and the inspector panel | `custom` mode, written by the retrieval tool with `get_stream_writer()` |
| `queries` | `{ items: [original, rewritten...] }` | Inspector panel (RAG-process view) | `custom` mode, same writer |
| `progress` | `{ message }` | Progress indicator on long tool calls | `custom` mode |
| `usage` | `{ promptTokens, completionTokens, cost, totalSpend }` | Usage badge, soft-cap warning | Last chunk of each model call, plus OpenRouter cost (see below) |
| `error` | `{ code, message }` | Inline error with retry | Backend |
| `done` | `{}` | End of stream | Backend |

This mapping was verified with a fake model in the spike ([research/python-stack-spike.md](research/python-stack-spike.md)). Not verified: real model streaming, and whether OpenRouter's `usage.cost` survives `langchain-openai`'s chunk conversion. If it is dropped, read it from the raw response, a small `ChatOpenAI` subclass, or `GET /api/v1/generation?id=<id>` (story 1 and 11 check this with a real key).

The same events feed logging, so the UI and the monitoring data cannot disagree.

Streaming operations:
- Send `X-Accel-Buffering: no` and `Cache-Control: no-cache`, and a `: keepalive` comment every 15 to 20 seconds while tools run.
- Do not add gzip middleware to the stream.
- In development, Vite proxies `/api` to the backend, so no CORS code is needed. Keep `CORSMiddleware` limited to `http://localhost:5173` as a fallback.
- A client disconnect cancels the generator, and the checkpoint may hold a partial turn. Untested, so story 6 includes a test.

## UI layout

Chat on the left, collapsible inspector panel on the right.

- Message list with DaisyUI `chat` bubbles, Citation chips under each answer, and attribution links (Wikipedia and OMT are CC BY-SA).
- Inline tool-call cards (name, arguments, result, duration, status).
- Inspector: rewritten queries, retrieved chunks with scores, tokens and cost, running spend against the caps.
- Progress indicators: a skeleton while retrieving, a spinner on running tool cards, a typing indicator while tokens stream.
- History sidebar (story 14) with JSON export.

## Cost guard

`usage_log` stores one row per model call (model, tokens, cost in credits). Before each request the backend sums cost. At 1 credit the UI shows a warning, at 4 credits the backend refuses new requests with a clear error. OpenRouter returns `usage.cost` on every response (verified at HTTP level in the JavaScript research), so no per-model price table is needed, subject to the `langchain-openai` check above. Credits are treated as USD (verify on the account page).

## Models

| Purpose | Model | Notes |
|---|---|---|
| Embeddings | `openai/text-embedding-3-small` | 1536 dimensions, about $0.02 per 1M tokens (per the research) |
| Answers and query rewriting | `openai/gpt-4o-mini` first | Tested end to end with tools and streaming through the JS client. Python `langchain-openai` is not yet tested with a real key. Compare cheaper tool-calling models with the tool-calling eval, and check workspace guardrails (one model was blocked on the account). |

Use `ChatOpenAI` and `OpenAIEmbeddings` from `langchain-openai` with `base_url="https://openrouter.ai/api/v1"`.

## Music tools

| Tool | Library |
|---|---|
| `chord_info` | `pychord` (MIT): notes, name, ambiguous detection from notes (D, F, A, C gives Dm7 and F6/D) |
| `scale_info` | `music21` (BSD-3): scales, modes, key signatures |
| `interval_between` | `music21`: quality, size, semitones, compound intervals |
| `transpose_for_instrument` | Hand-written offset table (with Citations) plus `music21` for note spelling |
| `note_frequency` | Hand-written maths (about 15 lines): frequency, MIDI number, nearest note, cents |

Rules: both libraries raise exceptions on invalid input (`H4`, `Xyz`), so tools wrap them and return structured errors. `music21` spells flats as `-` (`B-`), so output is normalised to `b`. `music21` is about 230 MB and takes about 1.4 s to import, which only affects the Docker image size and startup. `mingus` (GPLv3, last release 2020) and `musthe` (2018) are not used.

## Ingestion

A script, not the request path (`backend/scripts/ingest.py`):

1. Read `data/seed-list.json`.
2. Wikipedia pages: `GET /api/rest_v1/page/html/<title>` (keeps headings and tables, unlike `explaintext`), with a descriptive User-Agent and about 1 request per second. Parse `<section>` and heading elements with BeautifulSoup, strip images, references and navigation boxes, flatten tables to text rows. Resolve redirects and record Aliases.
3. Open Music Theory v1: `git clone --depth 1` the repo, read the Markdown files, strip front matter and image link definitions, split on `##` and `###`.
4. Apply the 5,000-character floor to Wikipedia pages, store `revision_id`, `license`, `url` per document.
5. Chunk, prepend the title and alias line, embed, and add to `PGVectorStore` with deterministic ids (a UUID derived from document, section and chunk index), so re-running upserts. After adding, delete that document's chunks whose ids are no longer produced. The library's batch insert is not one transaction (one INSERT and commit per row), so a failed run is fixed by re-running.

## Folder layout (proposed)

```
newDir/
  README.md
  CONTEXT.md
  docs/
  docker-compose.yml
  .env.example
  data/                      seed list, golden set, cached pages, OMT clone
  backend/
    pyproject.toml           pinned versions (langchain-postgres exact)
    app/
      main.py                FastAPI app, lifespan, CORS
      api/                   chat (SSE), threads, health
      agent/                 create_agent setup, prompts, checkpointer, streaming adapter
      rag/                   loaders, splitter, vector store, retriever, hybrid SQL
      tools/                 one module per tool plus schemas, instruments.py
      security/              validation, delimiting, rate limit
      db/                    engine config (two URL styles), migrations, usage and log writers
      config.py              settings from env
    scripts/                 ingest.py, run_eval.py
    eval/                    golden-set runners, RAGAs
    tests/
  frontend/
    package.json
    vite.config.ts           dev proxy for /api
    src/
      components/            Chat, MessageBubble, ToolCard, Inspector, Composer
      hooks/                 useChatStream (fetch + stream reader)
      state/                 conversation store
      types/                 event types shared with the backend contract
```

Rule: `backend/app/rag`, `tools`, `agent` and `security` never import FastAPI, so they run from scripts and tests. Only `api/` knows about HTTP.

## Tooling versions (from the research)

Backend spike versions (Python 3.12.3): `langchain-postgres` 0.0.19, `langchain` 1.4.6, `langchain-core` 1.6.12, `langgraph` 1.2.16, `langgraph-checkpoint-postgres` 3.2.0, `psycopg` 3.3.6, `fastapi` 0.149.0, `uvicorn` 0.54.0. Pin `langchain-postgres` to an exact version because 0.0.x APIs can change.

Frontend: Tailwind 4.3.3 and DaisyUI 5.7.50 install with `@import "tailwindcss"; @plugin "daisyui";` plus the `@tailwindcss/vite` plugin (per the research of the official install pages, no build was run). React and Vite versions are not yet researched, check at setup. This machine has Node 24, Docker 29 and Python 3.12.

Two database URL styles: `postgresql+psycopg://` for `PGEngine`, plain `postgresql://` for the checkpointer pool, which also needs `autocommit=True`, `prepare_threshold=0` and `dict_row`. Keep both in `db/engine.py`.

## Error handling

| Failure | Behaviour |
|---|---|
| Invalid input | 422 or 400 with a field-level message, nothing sent to the LLM |
| Model or network error | `error` event, retry with backoff once, then surface to the user |
| Tool error (invalid note, unknown instrument) | Libraries raise, so the tool catches and returns a structured error. The agent tells the user and does not invent data. |
| Empty retrieval | The agent says the knowledge base has nothing on it, no fallback to model memory |
| Budget cap reached | Request refused before any model call |
| Rate limit hit | 429 with retry-after |
| Client disconnect mid-stream | Generator cancelled, partial checkpoint possible (test in story 6) |
