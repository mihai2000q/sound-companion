# Architecture

## Overview

Two projects in one repository. A React single-page app (`sound-companion.client/`) talks to a FastAPI backend (`sound-companion.server/`) over one streaming endpoint. The backend owns all LangChain logic, the music tools, ingestion and evaluation. Postgres (with pgvector) holds the knowledge base, conversation memory, usage and logs.

```
Browser (React + Tailwind/shadcn/ui, Vite dev server; runs in compose, or on the host with `npm run dev`)
   |  POST /api/chat  (fetch, body: thread_id + message)      /api/* proxied by Vite to the backend
   |  <- SSE stream of typed events
FastAPI backend
   |-- input validation, rate limit (app/limits.py), budget guard
   |-- create_agent (LangChain)
   |      |-- tool: search_knowledge_base  -> Retriever -> Postgres (pgvector, + tsvector for hybrid)
   |      |-- tool: chord_info              -> pychord
   |      |-- tool: scale_info / interval_between -> music21
   |      |-- tool: transpose_for_instrument -> instrument table (+ music21 spelling)
   |      |-- tool: note_frequency           -> hand-written maths
   |-- AsyncPostgresSaver checkpointer (memory per thread_id)
   |-- usage + log + thread writers -> Postgres
   |-- GET /api/monitoring -> the monitoring views (daily latency and errors, calls per tool) plus tokens and credits from `usage_log` (per day and per model)
   |-- GET /api/threads -> the Conversations, newest first ({ thread_id, title, created_at })
   |-- GET /api/threads/{id} (messages), /export (JSON file), PATCH /api/threads/{id} (new title, decision 74), DELETE /api/threads/{id} (row + checkpoint, decision 69)
OpenRouter  (chat model, query-rewrite model, embeddings)
Eval scripts (pytest-style CLI, RAGAs) in the same Python project
```

## Request flow

1. The UI sends the user message and `thread_id`.
2. The backend validates input (length, characters), checks the rate limit, writes the `threads` row on the first request of a `thread_id` (title cut from the message, decision 68), and checks cumulative spend against the caps.
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

Behind a small `Retriever` interface in `sound-companion.server/app/rag/`:

- **Baseline (core):** `langchain-postgres` `PGVectorStore` (v2 API, `PGEngine`) with real metadata columns, used through `add_documents` and `similarity_search_with_score` (`VectorRetriever` in `app/rag/retriever.py`). `as_retriever` is not used because LangChain retrievers return documents without scores, and the metrics script and Citations need them. `retrieve(query, k, Filters(source_type, topics, topic_match, title))` returns `RetrievedChunk`s with the Citation fields and a similarity score (1 minus cosine distance, higher is better).
- **Hybrid (story 15, hard task):** `HybridRetriever` in `app/rag/hybrid.py`, our own SQL (dense top 20 plus `ts_rank` keyword top 20, fused with reciprocal rank fusion, constant 60, cut to `k`) run through psycopg. It takes the same `Filters` and returns the same `RetrievedChunk`s as the baseline, but `score` is the RRF score (at most 2/61), not a similarity. It is wired in by `RETRIEVER_MODE=hybrid` (`make_retriever` in `app/rag/factory.py`, default `vector`; an unknown value stops startup). See [DATABASE-SCHEMA.md](DATABASE-SCHEMA.md#hybrid-search-story-15). The library's `HybridSearchConfig` is a second mode for comparison only, because in `langchain-postgres` 0.0.19 it mutates the shared config and reuses the first query's keywords unless a fresh config copy is passed on every call (confirmed in the spike).
- **HNSW:** created with `apply_vector_index(HNSWIndex(...))`. A selective filter returned 0 rows with the index forced until `hnsw.iterative_scan = relaxed_order` was set through a small custom `QueryOptions` subclass, so we ship that class.

## Streaming events (SSE)

The backend returns `text/event-stream` from a FastAPI `StreamingResponse`. The browser reads it with `fetch` and a stream reader (`EventSource` only supports GET and cannot send a JSON body). Each message is `data: <json>\n\n`.

| Event `type` | Payload | UI use | Source in the agent stream |
|---|---|---|---|
| `token` | `{ text }` | Append to the answer | `messages` mode, `AIMessageChunk` with content |
| `tool_call` | `{ id, name, args }` | Show a tool card in "running" state | `updates` mode (complete call from the model node) |
| `tool_result` | `{ id, name, content, durationMs }` | Fill the tool card | `updates` mode (tools node) |
| `citations` | `{ items: [{ id, title, section, url, score, license, content }] }` (one per retrieved chunk, from stored metadata; `id` is the chunk id, `content` the chunk text) | Citation chips and the inspector panel | `custom` mode, written by the retrieval tool with `get_stream_writer()`. Not sent when the search finds nothing |
| `queries` | `{ items: [original, rewritten...] }` (the original query first, then the rewritten variants) | Inspector panel (RAG-process view) | `custom` mode, same writer. Not sent when the search finds nothing |
| `progress` | `{ message }` | Reserved: the client type exists, but the server sends no `progress` events today (the UI shows a skeleton and spinners from `tool_call` and `tool_result`) | `custom` mode, not emitted |
| `usage` | `{ promptTokens, completionTokens, cost, totalSpend, warning }` (`cost` and tokens are this request's so far, `totalSpend` is the `usage_log` sum, `warning` is set at the soft cap) | Usage badge, soft-cap warning | After each answer model call and each tool result, read from `usage_log` (also before an `error`, so a failed turn shows its spend) |
| `error` | `{ code, message }` (`agent_error`, `tool_limit` after 8 tool calls in one request, or `budget_exceeded` at the hard cap, sent without any model call) | Inline error with retry (no retry for `budget_exceeded`) | Backend |
| `done` | `{}` | End of stream | Backend |

This mapping was verified with a fake model in the spike ([research/python-stack-spike.md](research/python-stack-spike.md)). Real streaming and tool calling were then verified against OpenRouter (section C4 of the spike). `langchain-openai` drops `usage.cost` on streamed chunks, so the backend uses a small `ChatOpenAI` subclass that keeps the raw `usage` on the chunk (decision 46).

The same events feed logging, so the UI and the monitoring data cannot disagree.

Streaming operations:
- Send `X-Accel-Buffering: no` and `Cache-Control: no-cache`, and a `: keepalive` comment every 15 to 20 seconds while tools run.
- Do not add gzip middleware to the stream.
- In development, Vite proxies `/api` to the backend, so no CORS code is needed. `CORSMiddleware` allows only the client origin (`http://localhost:$CLIENT_PORT` and `http://127.0.0.1:$CLIENT_PORT`), `GET` and `POST`, as a fallback.
- A client disconnect cancels the generator, and the checkpoint holds the partial turn and the thread stays usable (decision 57, [research](research/python-stack-spike.md#c6-sse-endpoint-with-a-real-model-story-6-issue-35)).

## UI layout

Chat on the left, collapsible inspector panel on the right.

- Message list with hand-written Tailwind chat bubbles (shadcn has no chat component), Citation chips under each answer, and attribution links (Wikipedia and OMT are CC BY-SA).
- Inline tool-call cards (name, arguments, result, duration, status).
- Inspector: rewritten queries, retrieved chunks with scores, tokens and cost, running spend against the caps.
- Progress indicators: a skeleton while retrieving, a spinner on running tool cards, a typing indicator while tokens stream.
- History sidebar with JSON export, and a `/monitoring` page.

## Cost guard

`usage_log` stores one row per model call (model, tokens, cost in credits). Before each request the backend sums cost. At 1 credit the UI shows a warning, at 4 credits the backend refuses new requests with a clear error. OpenRouter returns `usage.cost` on every response (verified at HTTP level in the JavaScript research), so no per-model price table is needed, read through the `ChatOpenAI` subclass above. Credits are treated as USD (verify on the account page).

## Models

| Purpose | Model | Notes |
|---|---|---|
| Embeddings | `openai/text-embedding-3-small` | 1536 dimensions, about $0.02 per 1M tokens (per the research) |
| Answers | `openai/gpt-4o-mini` (`OPENROUTER_CHAT_MODEL`) | Tested end to end with tools and streaming. Cheaper tool-calling models were compared with the tool-calling eval, see [EVALUATION.md](EVALUATION.md). |
| Query rewriting | `openai/gpt-4o-mini` (`OPENROUTER_REWRITE_MODEL`) | Cheap model, separate setting |
| RAGAs judge | `google/gemini-2.5-flash-lite` (`OPENROUTER_JUDGE_MODEL`) | Scores exports, spend logged as `eval` |

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

A script, not the request path (`sound-companion.server/scripts/ingest.py`):

1. Read `data/seed-list.json`.
2. Wikipedia pages: `GET /api/rest_v1/page/html/<title>` (keeps headings and tables, unlike `explaintext`), with a descriptive User-Agent and about 1 request per second. Pages are cached under `data/cache/wikipedia/` (HTML plus a small JSON file with the canonical title and `revision_id`, read from the response `etag`), keyed by the requested title, so a re-run makes no requests. Parse the headings with BeautifulSoup, strip images, references, navigation boxes and infoboxes, flatten `wikitable`s to text rows with `rowspan` and `colspan` expanded. Redirects are followed, the canonical title is the document title and the requested name becomes an Alias.
3. Open Music Theory v1: `git clone --depth 1` the repo, read the Markdown files, strip front matter and link definitions, split on `#`, `##` and `###` into sections with a heading path. Site plumbing and stub pages are excluded and listed (`app/rag/omt.py`). The clone lives in `data/cache/omt/`.
4. Apply the 5,000-character floor to Wikipedia pages (required pages below it are kept and flagged), print the report of included, dropped and flagged entries, and upsert every document, with its sections, `revision_id`, `license` and `url`, into `documents` through SQLAlchemy (stale rows are removed in the same transaction).
5. `scripts.index` (a second script): chunk, prepend the title and alias line, embed, and add to `PGVectorStore` with deterministic ids (a UUID derived from document, section and chunk index), so re-running upserts. After adding, delete that document's chunks whose ids are no longer produced. The library's batch insert is not one transaction (one INSERT and commit per row), so a failed run is fixed by re-running.

## Folder layout

```
sound-companion/
  README.md, CONTEXT.md, CLAUDE.md
  docs/
  docker-compose.yml
  .env.example
  data/                      seed-list.json, golden-set.json, golden-tools.json, injection-tests.json,
                             runs/ (RAGAs exports); cache/ (gitignored): fetched pages, OMT clone
  sound-companion.server/
    pyproject.toml           pinned versions (langchain-postgres exact), `ragas` dependency group
    app/
      main.py                FastAPI app, lifespan (migrations, agent, checkpointer), CORS
      config.py              settings from env
      limits.py              message limits, rate limiter, tool-call cap
      api/                   chat (SSE), threads, monitoring, health
      agent/                 create_agent setup, prompt, checkpointer (memory.py), streaming adapter, request log,
                             history, Convention check, run export, tool and injection eval runners
      rag/                   Wikipedia fetch and cleaning, OMT parser, corpus build, document store, chunking,
                             embeddings, vector store, Retriever, hybrid SQL, rewrite, injection scan, eval metrics
      tools/                 one module per music tool, search tool, registry, delimit (data wrappers), instruments table
      security/              redact (secret masking for app_logs)
      db/                    SQLAlchemy models, Alembic migrations and runner, usage, log and thread writers
    scripts/                 ingest, chunk, setup_chunks, index, scan_injection, search, eval_retrieval, eval_tools,
                             eval_injection, compare_runs, export_run, plus small check and spike scripts
    eval/                    run_ragas.py, judge.py, results/ (saved runs)
    tests/
  sound-companion.client/
    package.json
    vite.config.ts           dev proxy for /api
    src/
      App.tsx, providers.tsx, router.tsx   app shell, context providers, route table
      pages/                 HomePage (/), MonitoringPage (/monitoring)
      components/            Conversation, Sidebar, MessageList, Inspector, Composer, UsageBadge
      hooks/                 useChatStream (fetch + stream reader)
      queries/               React Query keys and queryOptions per feature
      lib/                   citations, conversation and tool-result helpers
      types/                 event and API types shared with the backend contract
```

Rule: `sound-companion.server/app/rag`, `tools`, `agent` and `security` never import FastAPI, so they run from scripts and tests. Only `api/` knows about HTTP.

## Tooling versions (from the research)

Backend spike versions (Python 3.12.3): `langchain-postgres` 0.0.19, `langchain` 1.4.6, `langchain-core` 1.6.12, `langgraph` 1.2.16, `langgraph-checkpoint-postgres` 3.2.0, `psycopg` 3.3.6, `fastapi` 0.149.0, `uvicorn` 0.54.0. Pin `langchain-postgres` to an exact version because 0.0.x APIs can change.

Frontend: Tailwind 4.3.3 installs with `@import "tailwindcss";` plus the `@tailwindcss/vite` plugin (per the research of the official install pages, no build was run). React and Vite versions are not yet researched, check at setup. This machine has Node 24, Docker 29 and Python 3.12.

Two database URL styles: `postgresql+psycopg://` for `PGEngine`, plain `postgresql://` for the checkpointer pool, which also needs `autocommit=True`, `prepare_threshold=0` and `dict_row`. Both are built from `app/config.py` (`database_url`, `database_url_async`).

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
