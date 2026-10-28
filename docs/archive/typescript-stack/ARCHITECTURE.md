# Architecture

## Overview

One SvelteKit app serves the UI and the API. The server side owns all LangChain logic. Postgres (with pgvector) holds the knowledge base, conversation memory, usage and logs. A separate Python container runs RAGAs offline.

```
Browser (Svelte 5 + shadcn/ui)
   |  POST /api/chat  (fetch, body: thread_id + message)
   |  <- SSE stream of typed events
SvelteKit server (+server.ts)
   |-- input validation, rate limit, budget guard
   |-- createAgent (LangChain.js)
   |      |-- tool: search_knowledge_base  -> Retriever -> Postgres (pgvector, later + tsvector)
   |      |-- tool: chord_info / scale_info / interval_between   -> tonal
   |      |-- tool: transpose_for_instrument -> tonal + instrument table
   |      |-- tool: note_frequency           -> tonal + hand-written maths
   |-- PostgresSaver checkpointer (memory per thread_id)
   |-- usage + log writers -> Postgres
OpenRouter  (chat model, query-rewrite model, embeddings)
Eval container (Python, RAGAs) <- exported JSON
```

## Request flow

1. The UI sends the user message and `thread_id`.
2. The server validates input (length, characters), checks the rate limit, and checks cumulative spend against the caps.
3. The agent receives the message with the system prompt (see [DOMAIN.md](DOMAIN.md#bot-behaviour)).
4. The model decides whether to call tools. For explanations it calls `search_knowledge_base`. For calculations it calls a music tool.
5. `search_knowledge_base` rewrites the query into several variants (cheap model), retrieves for each variant, merges and de-duplicates, and returns chunks wrapped as data (see [SECURITY.md](SECURITY.md)).
6. For comparisons the model may call tools several times (this is decomposition).
7. Tool results state their Convention (scientific pitch notation). If a retrieved Citation uses another Convention, the answer shows both.
8. The final answer streams as tokens, with Citations that reference retrieved chunks or tool results.
9. Token usage and cost are written to `usage_log`, and a `usage` event closes the stream.

## Query translation and structured retrieval

| Technique | Where it lives |
|---|---|
| Multi-query rewrite | Inside `search_knowledge_base`, using the cheap model |
| Decomposition | Agent loop: the model calls tools several times, guided by the system prompt |
| Structured retrieval | Typed arguments of `search_knowledge_base` (`source_type`, `topic`, `title`) turned into metadata filters (`PGVectorStore` supports equality, `in` and `arrayContains`) |
| Not used | HyDE and step-back (low value for factual questions, extra cost) |

## Retrieval

Behind a small `Retriever` interface in `src/lib/server/rag/`:

- **Baseline (core):** `PGVectorStore` from `@langchain/pgvector`, used with `add_documents` and `asRetriever({ k, filter })`, the pattern from the course.
- **Hybrid (story 15, hard task):** a custom `BaseRetriever` running the SQL in [DATABASE-SCHEMA.md](DATABASE-SCHEMA.md#hybrid-search-story-15-only): vector similarity plus `ts_rank`, fused with reciprocal rank fusion. The JS package has no hybrid mode and `BM25Retriever` is in-memory and in a deprecated package (per the research).

## Streaming events (SSE)

The server returns `content-type: text/event-stream`. The browser reads it with `fetch` and a stream reader (`EventSource` only supports GET). Each message is `data: <json>\n\n`.

| Event `type` | Payload | UI use | Source in the agent stream |
|---|---|---|---|
| `token` | `{ text }` | Append to the answer | `messages` stream mode |
| `tool_call` | `{ id, name, args }` | Show a tool card in "running" state | `messages` mode (tool-call chunks) |
| `tool_result` | `{ id, name, result, durationMs }` | Fill the tool card | `updates` mode (the tools update carries the tool message) |
| `citations` | `{ chunks: [{ id, title, section, url, score }] }` | Citation chips and the inspector panel | Tool result of `search_knowledge_base` |
| `queries` | `{ original, rewritten[] }` | Inspector panel (RAG-process view) | Tool result of `search_knowledge_base` |
| `usage` | `{ promptTokens, completionTokens, cost, totalSpend }` | Usage badge, soft-cap warning | OpenRouter `usage` on the last chunk |
| `error` | `{ code, message }` | Inline error with retry | Server |
| `done` | `{}` | End of stream | Server |

Per the research, `streamMode: ["messages","updates"]` gives tokens, tool-call chunks and tool results. A `custom` stream mode and a newer `streamEvents` v3 exist and were not run, so confirm the exact mapping in story 6. `cost` is in OpenRouter credits.

The same events feed logging, so the UI and the monitoring data cannot disagree.

## UI layout

Chat on the left, collapsible inspector panel on the right.

- Message list with Tailwind chat bubbles, Citation chips under each answer, and attribution links (Wikipedia and OMT are CC BY-SA).
- Inline tool-call cards (name, arguments, result, duration, status).
- Inspector: rewritten queries, retrieved chunks with scores, tokens and cost, running spend against the caps.
- Progress indicators: a skeleton while retrieving, a spinner on running tool cards, a typing indicator while tokens stream.
- History sidebar (story 14) with JSON export.

## Cost guard

`usage_log` stores one row per model call (model, tokens, cost in credits). Before each request the server sums cost. At 1 credit the UI shows a warning, at 4 credits the server refuses new requests with a clear error. `usage.cost` comes from OpenRouter on every response, so no per-model price table is needed. Credits are treated as USD (verify on the account page).

## Models

| Purpose | Model | Notes |
|---|---|---|
| Embeddings | `openai/text-embedding-3-small` | 1536 dimensions, about $0.02 per 1M tokens (per the research) |
| Answers and query rewriting | `openai/gpt-4o-mini` first | The only model tested end to end with tools and streaming. Compare cheaper tool-calling models with the tool-calling eval, and check workspace guardrails (the research found one model blocked on the account). |

`ChatOpenAI` and `OpenAIEmbeddings` with `configuration.baseURL = "https://openrouter.ai/api/v1"` worked in the research, including tool calling and streaming through `createAgent`.

## Ingestion

A script, not the request path (`scripts/ingest.ts`):

1. Read `data/seed-list.json`.
2. Wikipedia pages: `GET /api/rest_v1/page/html/<title>` (keeps headings and tables, unlike `explaintext`), with a descriptive User-Agent and about 1 request per second. Parse `<section>` and heading elements, strip images, references and navigation boxes, flatten tables to text rows. Resolve redirects and record Aliases.
3. Open Music Theory v1: `git clone --depth 1` the repo, read the Markdown files, strip front matter and image link definitions, split on `##` and `###`.
4. Apply the 5,000-character floor to Wikipedia pages, store `revision_id`, `license`, `url` per document.
5. Chunk, prepend the title and alias line, embed, and write to `documents` and `chunks`. Re-running is idempotent.

## Folder layout (proposed)

```
newDir/
  README.md
  CONTEXT.md
  docs/
  docker-compose.yml
  .env.example
  data/                      seed list, golden set, cached pages, OMT clone
  scripts/                   ingestion and evaluation CLIs
  src/
    lib/
      server/
        rag/                 loaders, splitter, retriever, index
        tools/               one file per tool plus schemas, instruments.ts
        agent/               createAgent setup, prompts, checkpointer
        security/            validation, delimiting, rate limit
        db/                  pg client, migrations, usage and log writers
        config.ts            env parsing
      components/            Svelte components (chat, tool card, inspector)
      stores/                Svelte 5 state modules
      types/                 shared event and domain types
    routes/
      +page.svelte           chat page
      api/chat/+server.ts    SSE endpoint
      api/threads/...        history and export
  eval/                      Python RAGAs container
  tests/
```

Rule: everything under `src/lib/server/` is framework-agnostic and imports nothing from SvelteKit, so it can run from scripts and tests, and the UI shell could be swapped.

## Tooling versions (from the research)

Tailwind 4.3.3 installs with `@import "tailwindcss";` plus the `@tailwindcss/vite` plugin. SvelteKit 3.1 needs Node 22.17+, Vite 8 and TypeScript 6. The research agent did not run a build. This machine has Node 24, Docker 29 and Python 3.12.

## Error handling

| Failure | Behaviour |
|---|---|
| Invalid input | 400 with a field-level message, nothing sent to the LLM |
| Model or network error | `error` event, retry with backoff once, then surface to the user |
| Tool error (invalid note, unknown instrument) | Tool returns a structured error. `tonal` returns empty results for invalid input instead of throwing, so tools check for empty results. The agent tells the user and does not invent data. |
| Empty retrieval | The agent says the knowledge base has nothing on it, no fallback to model memory |
| Budget cap reached | Request refused before any model call |
| Rate limit hit | 429 with retry-after |
