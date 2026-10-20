# Architecture

## Overview

One SvelteKit app serves the UI and the API. The server side owns all LangChain logic. Postgres (with pgvector) holds the knowledge base, conversation memory, usage and logs. A separate Python container runs RAGAs offline.

```
Browser (Svelte 5 + DaisyUI)
   |  POST /api/chat  (fetch, body: thread_id + message)
   |  <- SSE stream of typed events
SvelteKit server (+server.ts)
   |-- input validation, rate limit, budget guard
   |-- createAgent (LangChain.js)
   |      |-- tool: search_knowledge_base  -> Retriever -> Postgres (pgvector + tsvector)
   |      |-- tool: musicbrainz_discography -> MusicBrainz API (1 req/s)
   |      |-- tool: discography_stats       -> pure function
   |      |-- tool: compare_discographies   -> uses musicbrainz_discography
   |-- PostgresSaver checkpointer (memory per thread_id)
   |-- usage + log writers -> Postgres
OpenRouter  (chat model, query-rewrite model, embeddings)
Eval container (Python, RAGAs) <- exported JSON
```

## Request flow

1. The UI sends the user message and `thread_id`.
2. The server validates input (length, characters), checks the rate limit, and checks cumulative spend against the caps.
3. The agent receives the message with the system prompt (see [DOMAIN.md](DOMAIN.md#bot-behaviour)).
4. The model decides whether to call tools. For knowledge questions it calls `search_knowledge_base`.
5. `search_knowledge_base` rewrites the query into several variants (cheap model), retrieves for each variant, merges and de-duplicates, and returns chunks wrapped as data (see [SECURITY.md](SECURITY.md)).
6. For structured questions ("releases between 1995 and 2000") the model calls `musicbrainz_discography` with year parameters.
7. For comparisons the model may call tools several times (this is decomposition).
8. The final answer streams as tokens, with citations that reference retrieved chunks.
9. Token usage and cost are written to `usage_log`, and a `usage` event closes the stream.

## Query translation and structured retrieval

| Technique | Where it lives |
|---|---|
| Multi-query rewrite | Inside `search_knowledge_base`, using the cheap model |
| Decomposition | Agent loop: the model calls tools several times, guided by the system prompt |
| Structured retrieval | Typed arguments of `search_knowledge_base` (`subgenre`, `entity_type`, `entity`) turned into metadata filters |
| Not used | HyDE and step-back (low value for factual artist questions, extra cost) |

## Retrieval

Behind a small `Retriever` interface in `src/lib/server/rag/`:

- **Baseline:** `PGVectorStore.asRetriever({ k, filter })`.
- **Hybrid (story 15):** BM25 retriever plus the vector retriever combined with `EnsembleRetriever` (reciprocal rank fusion). Band names like "Opeth" or "Mgla" benefit from keyword matching, concept questions benefit from embeddings.
- **Fallback:** a single SQL query combining `<=>` vector distance and `ts_rank`, fused by RRF, written by hand.

To verify when implementing: hybrid configuration in `@langchain/pgvector`, and whether `EnsembleRetriever` and `BM25Retriever` exist in the installed LangChain.js version.

## Streaming events (SSE)

The server returns `content-type: text/event-stream`. The browser reads it with `fetch` and a stream reader (`EventSource` only supports GET). Each message is `data: <json>\n\n`.

| Event `type` | Payload | UI use |
|---|---|---|
| `token` | `{ text }` | Append to the answer |
| `tool_call` | `{ id, name, args }` | Show a tool card in "running" state |
| `tool_result` | `{ id, name, result, durationMs }` | Fill the tool card |
| `citations` | `{ chunks: [{ id, entity, section, url, score }] }` | Citation chips and the inspector panel |
| `queries` | `{ original, rewritten[] }` | Inspector panel (RAG-process view) |
| `usage` | `{ promptTokens, completionTokens, costEur, totalSpendEur }` | Usage badge, soft-cap warning |
| `error` | `{ code, message }` | Inline error with retry |
| `done` | `{}` | End of stream |

The same events feed logging, so the UI and the monitoring data cannot disagree.

## UI layout

Chat on the left, collapsible inspector panel on the right.

- Message list with DaisyUI `chat` bubbles, citation chips under each answer.
- Inline tool-call cards (name, arguments, result, duration, status).
- Inspector: rewritten queries, retrieved chunks with scores, tokens and cost, running spend against the caps.
- Progress indicators: a skeleton while retrieving, a spinner on running tool cards, a typing indicator while tokens stream.
- History sidebar (story 14) with JSON export.

## Cost guard

`usage_log` stores one row per model call (model, tokens, cost). Before each request the server sums cost. At 1 EUR the UI shows a warning, at 4 EUR the server refuses new requests with a clear error. Cost per call comes from OpenRouter's usage fields where available, otherwise from per-model prices in config (verify at setup).

## Folder layout (proposed)

```
newDir/
  README.md
  docs/
  docker-compose.yml
  .env.example
  data/                      seed list, golden set, cached downloads
  scripts/                   ingestion and evaluation CLIs
  src/
    lib/
      server/
        rag/                 loaders, splitter, retriever, index
        tools/               one file per tool plus schemas
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

## Error handling

| Failure | Behaviour |
|---|---|
| Invalid input | 400 with a field-level message, nothing sent to the LLM |
| Model or network error | `error` event, retry with backoff once, then surface to the user |
| Tool failure (MusicBrainz down, 503, timeout) | Tool returns a structured error, the agent tells the user what failed and does not invent data |
| Empty retrieval | The agent says the knowledge base has nothing on it, no fallback to model memory |
| Budget cap reached | Request refused before any model call |
| Rate limit hit | 429 with retry-after |
