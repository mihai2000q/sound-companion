# Implementation plan

Work story by story. Each story is a vertical slice that can be demonstrated and tested before the next starts. No day estimates. Stories 1 to 9 deliver the core requirements, the rest add the optional tasks and reflection.

Each story states: goal, what to build, acceptance criteria, and facts to verify first.

## Core requirement coverage

| Brief requirement | Stories |
|---|---|
| Knowledge base, chunking, embeddings, similarity search | 2, 3, 4 |
| At least 3 tool calls | 5, 8 |
| Domain specialisation and prompts | 5, 10 |
| Security measures | 13 (plus validation in 6 and 8) |
| LangChain with OpenRouter | 1, 5 |
| Error handling and input validation | 6, 8 |
| UI with context, sources, tool results, progress | 6, 7, 9 |
| Query translation and structured retrieval | 5, 10 |

| Optional task | Story |
|---|---|
| Source citations (easy) | 7 |
| Conversation history and export (easy) | 14 |
| RAG-process visualisation (easy, stretch) | 7 |
| Prompt-injection protection (medium) | 13 |
| Token usage and cost display (medium) | 11 |
| Logging and monitoring (medium) | 12 |
| Hybrid search (hard) | 15 |
| RAGAs evaluation (hard) | 16 |

---

## Story 1: Infrastructure and scaffold

**Build:** `docker-compose.yml` with Postgres (`pgvector` image) and a volume. SvelteKit + TypeScript scaffold, Tailwind + shadcn/ui, `.env.example`, `src/lib/server/config.ts` parsing env with validation, migration runner with the first migration (`CREATE EXTENSION vector`).

**Verify first:** Tailwind and shadcn/ui versions work together. Pick chat model, rewrite model and embedding model on OpenRouter (tool-calling support, prices, embedding dimension).

**Done when:**
- `docker compose up` starts Postgres, migrations apply, `\dx` shows `vector`.
- `npm run dev` serves a page styled with shadcn/ui.
- App fails fast with a clear message when a required env var is missing.
- A one-off script calls OpenRouter chat and embeddings successfully and logs usage.

## Story 2: Seed list and ingestion spike

**Build:** `data/seed-list.json` (about 120 Artists, about 40 Genre and History articles, see [DOMAIN.md](DOMAIN.md) and [CONTEXT.md](../CONTEXT.md)), reviewed by the author. Script that loads the `music-wiki` snapshot, joins it to the seed list by name or MBID, reports coverage, and fetches missing entries from the Wikipedia API.

**Verify first:** snapshot coverage of metal bands, Wikipedia text and dataset licences, MusicBrainz terms.

**Done when:**
- Coverage report lists matched, missing and filled entries.
- At least 90 percent of seed entries have text of usable length.
- Every stored document has `url` and `license`.
- Licence findings are written into DOMAIN.md.

## Story 3: Chunking, embeddings, indexing

**Build:** section-aware splitter (heading in chunk text, then recursive splitter about 800 chars, 100 overlap), metadata as in DOMAIN.md, embedding via OpenRouter, indexing into `documents` and `chunks`, idempotent re-run.

**Verify first:** the table layout `PGVectorStore` expects, versus [DATABASE-SCHEMA.md](DATABASE-SCHEMA.md). Adjust either.

**Done when:**
- One command builds the index from the seed data.
- Re-running does not duplicate rows.
- Total embedding cost is logged and within a few cents.
- A sample query returns plausible chunks in a REPL script.

## Story 4: Baseline retrieval, golden set v0, retrieval metrics

**Build:** `Retriever` interface and a `PGVectorStore.asRetriever` implementation with metadata filters. `data/golden-set.json` with at least 10 questions that have `expected_sources`. Script computing precision@5 and recall@5.

**Done when:**
- Retrieval script prints metrics per question and overall.
- Filters (`subgenre`, `entity_type`, `entity`) change the results as expected.
- Metrics are saved so later stories can compare.

## Story 5: Agent with retrieval tool and memory

**Build:** `search_knowledge_base` tool (zod schema, clear description), `createAgent` with the system prompt from DOMAIN.md, `PostgresSaver` checkpointer with `thread_id`. A CLI chat script for testing without the UI.

**Verify first:** PostgresSaver JS API, `createAgent` import and options in the installed LangChain.js.

**Done when:**
- Asking about a seed band returns a grounded answer with cited entities.
- A follow-up question uses memory of the earlier turn.
- An off-topic question gets a polite decline with no tool call.
- The agent refuses to answer from model memory when retrieval is empty.

## Story 6: SSE chat endpoint and streaming UI

**Build:** `POST /api/chat` with validation (zod), typed SSE events as in [ARCHITECTURE.md](ARCHITECTURE.md), Svelte chat page with composer, message list, typing indicator, error display. Svelte state module for the stream.

**Done when:**
- Tokens stream into the page as they arrive.
- Invalid input returns 400 and shows a field-level message.
- A model error shows an `error` event with a retry option.
- Opening a new chat creates a new `thread_id`.

## Story 7: Citations and inspector panel

**Build:** `citations` and `queries` events, citation chips under answers linking to the source URL, collapsible inspector panel (retrieved chunks with scores, original and rewritten queries). The panel is the RAG-process visualisation.

**Done when:**
- Every factual sentence in a sample answer maps to a visible citation.
- Clicking a chip highlights the chunk in the inspector.
- The panel shows the pipeline for the latest answer.

## Story 8: MusicBrainz tools

**Build:** `musicbrainz_discography`, `discography_stats`, `compare_discographies` with zod schemas, a rate-limited client (1 request per second queue, timeout, User-Agent, host allow-list), unit tests with recorded fixtures.

**Verify first:** MusicBrainz response shape for release groups, release types and dates, and its current terms.

**Done when:**
- Unit tests pass without network access.
- A real lookup for a known Artist returns one row per Release (not per Edition), filtered by year range.
- By default only studio albums and EPs are returned, and the output lists which types were included.
- Passing other release types includes them.
- Two rapid calls never exceed 1 request per second.
- MusicBrainz failure returns a structured error and the agent reports it without inventing data.

## Story 9: Tool-call cards and tool-calling eval

**Build:** `tool_call` and `tool_result` events rendered as cards (name, args, result, duration, status). The tool-calling evaluation script from [EVALUATION.md](EVALUATION.md) with at least 15 cases including no-tool cases.

**Done when:**
- Cards update from running to done.
- Evaluation prints tool selection and parameter accuracy per difficulty.
- Failing cases lead to improved tool descriptions, with before and after numbers recorded.

## Story 10: Query translation and disputed-claims behaviour

**Build:** multi-query rewrite inside `search_knowledge_base` (cheap model, merge and de-duplicate), prompt rules for decomposition and for disputed facts, `queries` event.

**Done when:**
- "What was the first metal song?" returns several cited candidates and says it is disputed.
- A comparison question triggers several tool calls.
- Retrieval metrics with and without rewriting are compared and recorded.

## Story 11: Usage, cost and budget guard

**Build:** write a `usage_log` row for every model call (answer, rewrite, embed), `usage` event, usage badge, soft cap warning at 1 EUR, hard cap refusal at 4 EUR.

**Verify first:** how OpenRouter reports usage and cost, and whether streaming responses include it.

**Done when:**
- Total spend shown in the UI matches the database sum.
- Setting the caps to tiny values in config triggers the warning and the refusal.
- Refused requests make no model call.

## Story 12: Logging and monitoring

**Build:** structured logger writing to `app_logs` (request id, tool calls, retrieval, errors, injection flags, budget blocks), a simple read-only page or SQL views for latency, error rate and tool usage.

**Done when:**
- One request can be traced end to end by `request_id`.
- A saved SQL view or page shows average latency, error count and calls per tool.
- Logs contain no API keys or full prompts.

## Story 13: Prompt-injection protection

**Build:** delimiting and escaping of retrieved text and tool output, system-prompt rules, input limits, per-process rate limit, maximum tool calls per request, `data/injection-tests.json` and a runner (see [SECURITY.md](SECURITY.md)).

**Done when:**
- All injection tests pass, including the planted-chunk case.
- The runner prints pass/fail per case and is repeatable.
- Oversized input is rejected before any model call.

## Story 14: Conversation history and export

**Build:** `threads` table, sidebar listing conversations, switching between threads, JSON export of a thread (messages, sources, tool calls, usage).

**Verify first:** how to read message state from the checkpointer for a thread.

**Done when:**
- Reloading the page restores the conversation list.
- Exported JSON re-imports into a script for inspection.
- Deleting a thread removes it from the list.

## Story 15: Hybrid search

**Build:** BM25 plus vector retrieval combined by RRF (`EnsembleRetriever`, or the SQL fallback), switchable by config, compared against baseline on the golden set.

**Verify first:** `@langchain/pgvector` hybrid API, `EnsembleRetriever` and `BM25Retriever` availability.

**Done when:**
- Exact-name queries ("Who is Mgla?") improve over vector-only.
- A table of precision@5 and recall@5 for baseline vs hybrid is saved.
- The decision on which mode is default is recorded in DECISIONS.md.

## Story 16: RAGAs evaluation

**Build:** run export script (question, answer, contexts, reference), `eval/` Python container with `run_ragas.py`, golden set of about 30 questions, results section in EVALUATION.md.

**Done when:**
- `docker compose run eval` prints all four RAGAs metrics.
- Results are compared to the targets (faithfulness 0.8 or above, context metrics 0.7 or above) and low cases are explained.
- Total evaluation spend is logged.

## Story 17: Final pass

**Build:** update all docs to match reality, a demo script (the questions to show, including the disputed-history and injection cases), a reflection section covering known problems and improvement ideas, a clean-clone setup check.

**Done when:**
- A fresh clone starts with `docker compose up` and the README steps.
- The demo script runs end to end.
- The reflection names real failure cases found during evaluation.

## Stretch (only if everything above is done)

Live API refresh of the knowledge base, a `find_band_members` tool, a "similar artists" feature, multi-model switching.
