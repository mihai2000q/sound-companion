# Implementation plan

Work story by story. Each story is a vertical slice that can be demonstrated and tested before the next starts. No day estimates. Stories 1 to 9 deliver the core requirements, the rest add the optional tasks and reflection.

Each story states: goal, what to build, acceptance criteria, and facts to verify first. Terms follow [CONTEXT.md](../CONTEXT.md).

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

**Build:** `docker-compose.yml` with Postgres (`pgvector` image) and a volume. SvelteKit + TypeScript scaffold, Tailwind 4 + DaisyUI 5 (`@plugin "daisyui"`), `.env.example`, `src/lib/server/config.ts` parsing env with validation, migration runner with the first migration (`CREATE EXTENSION vector`).

**Verify first:** a Tailwind 4, DaisyUI 5 and SvelteKit 3 build works (Node 22.17+, Vite 8, TypeScript 6). Check OpenRouter workspace guardrails and that credits equal USD on the account page. Confirm `openai/text-embedding-3-small` and `openai/gpt-4o-mini` work with tool calling and streaming on this account.

**Done when:**
- `docker compose up` starts Postgres, migrations apply, `\dx` shows `vector`.
- `npm run dev` serves a page styled with DaisyUI.
- App fails fast with a clear message when a required env var is missing.
- A one-off script calls OpenRouter chat and embeddings successfully and logs usage and cost.

## Story 2: Seed list and ingestion

**Build:** `data/seed-list.json` (about 60 theory articles, about 90 instrument articles, supporting pages, see [DOMAIN.md](DOMAIN.md)), reviewed by the author. `scripts/ingest.ts` stage one: fetch Wikipedia pages from the REST HTML endpoint (about 1 request per second, User-Agent, caching under `data/cache/`), `git clone --depth 1` Open Music Theory v1, parse sections, strip noise, apply the 5,000-character floor, resolve redirects into Aliases, record `revision_id`.

**Verify first:** table extraction for the "Transposing instrument" article and any tuning tables, the Wikipedia API rate-limit policy page, and the OMT licence statement (footer and about page, the repo has no LICENSE file).

**Done when:**
- A report lists included, dropped (below the floor) and flagged entries.
- Every stored document has `url`, `license`, `revision_id` and `source_type`.
- The transposing-instrument table survives extraction in readable form, or the plan to hand-build it is recorded.
- Re-running uses the cache and makes no new requests.

## Story 3: Chunking, embeddings, indexing

**Build:** section-aware splitter (title and alias line first, heading path as `section`, about 800 characters with 100 overlap), embedding through OpenRouter, a migration that owns the `chunks` DDL and the HNSW index, indexing into `documents` and `chunks` through `PGVectorStore.addDocuments`. Re-runs delete a document's chunks by `document_id` and re-add them in one transaction, because the store has no upsert.

**Verify first:** the TypeScript build with `PGVectorStore` and the `columns` option, and the spike's untested areas (real embeddings, the full table size). See [research/pgvectorstore-spike.md](research/pgvectorstore-spike.md).

**Done when:**
- One command builds the index from the cached pages.
- Re-running does not duplicate rows.
- Total embedding cost is logged and within a few cents.
- A sample query returns plausible chunks in a REPL script, and a query for "English horn" finds Cor anglais chunks.

## Story 4: Baseline retrieval, golden set v0, retrieval metrics

**Build:** `Retriever` interface with a `PGVectorStore.asRetriever` implementation and metadata filters (`source_type`, `topics`, `title`). `data/golden-set.json` with at least 10 questions that have `expected_sources`. Script computing precision@5 and recall@5.

**Done when:**
- Retrieval script prints metrics per question and overall.
- Filters change the results as expected.
- Metrics are saved so later stories can compare.

## Story 5: Agent with retrieval tool and memory

**Build:** `search_knowledge_base` tool (zod schema, clear description), `createAgent` with the system prompt from DOMAIN.md, `PostgresSaver` with `thread_id`. A CLI chat script for testing without the UI.

**Verify first:** `PostgresSaver` against the real database (`fromConnString`, `setup()`), `createAgent` import from `langchain`, and `agent.getState` returning messages.

**Done when:**
- Asking about a seed topic returns a grounded answer with Citations.
- A follow-up question uses memory of the earlier turn.
- An off-topic question gets a polite decline with no tool call.
- The agent says so when retrieval is empty and does not answer from model memory.

## Story 6: SSE chat endpoint and streaming UI

**Build:** `POST /api/chat` with validation (zod), typed SSE events as in [ARCHITECTURE.md](ARCHITECTURE.md), Svelte chat page with composer, message list, typing indicator, error display. Svelte state module for the stream.

**Verify first:** the stream-mode mapping for each event (`messages`, `updates`, and how `citations` and `queries` leave the tool).

**Done when:**
- Tokens stream into the page as they arrive.
- Invalid input returns 400 and shows a field-level message.
- A model error shows an `error` event with a retry option.
- Opening a new chat creates a new `thread_id`.

## Story 7: Citations and inspector panel

**Build:** `citations` and `queries` events, Citation chips under answers linking to the source page with a CC BY-SA attribution line, collapsible inspector panel (retrieved chunks with scores, original and rewritten queries). The panel is the RAG-process visualisation.

**Done when:**
- Every factual sentence in a sample answer maps to a visible Citation.
- Clicking a chip highlights the chunk in the inspector.
- Citation URLs come from stored metadata, not from model text.

## Story 8: Music tools

**Build:** `chord_info`, `scale_info`, `interval_between`, `transpose_for_instrument` (with the cited table of about 14 instruments in `instruments.ts`), `note_frequency`, all with zod schemas and a structured-error path for empty `tonal` results. Unit tests with the expected values from [EVALUATION.md](EVALUATION.md).

**Done when:**
- Unit tests pass without network access.
- `chord_info` returns both Candidates for D, F, A, C (Dm7 and F6/D).
- A B-flat clarinet reading a written C4 gives Bb3, and 450 Hz gives A4 plus about 39 cents.
- Invalid input ("H99", an unknown instrument) returns a structured error, not a guess.
- `transpose_for_instrument` returns the Citation for the instrument's transposition.
- Every tool states its Convention (C4 = middle C).

## Story 9: Tool-call cards and tool-calling eval

**Build:** `tool_call` and `tool_result` events rendered as cards (name, args, result, duration, status). The tool-calling evaluation script from [EVALUATION.md](EVALUATION.md) with at least 15 cases including no-tool cases.

**Done when:**
- Cards update from running to done.
- Evaluation prints tool selection and parameter accuracy per difficulty.
- Failing cases lead to improved tool descriptions, with before and after numbers recorded.
- A cheaper model is compared with `gpt-4o-mini` on the same set.

## Story 10: Query translation and Convention-conflict behaviour

**Build:** multi-query rewrite inside `search_knowledge_base` (cheap model, merge and de-duplicate), prompt rules for decomposition, Convention conflicts and Candidates, `queries` event.

**Done when:**
- "What is middle C called, and what do Germans call B-flat?" shows each Convention with its own Citation and says they differ.
- A comparison question triggers several tool calls.
- Retrieval metrics with and without rewriting are compared and recorded.

## Story 11: Usage, cost and budget guard

**Build:** write a `usage_log` row for every model call (answer, rewrite, embed), `usage` event, usage badge, soft cap warning at 1 credit, hard cap refusal at 4 credits.

**Verify first:** that `usage.cost` is present on streamed responses (last chunk) through `createAgent` and on embeddings.

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

**Build:** delimiting and escaping of retrieved text and tool output, system-prompt rules, input limits, per-process rate limit, maximum tool calls per request, the ingestion scan for instruction-like strings, `data/injection-tests.json` and a runner (see [SECURITY.md](SECURITY.md)).

**Done when:**
- All injection tests pass, including the planted-chunk case.
- The runner prints pass/fail per case and is repeatable.
- Oversized input is rejected before any model call.

## Story 14: Conversation history and export

**Build:** `threads` table, sidebar listing Conversations, switching between them, JSON export of a Conversation (messages, Citations, tool calls, usage).

**Verify first:** reading message state from the checkpointer for a thread (`getState`).

**Done when:**
- Reloading the page restores the Conversation list.
- Exported JSON re-imports into a script for inspection.
- Deleting a Conversation removes it from the list.

## Story 15: Hybrid search

**Build:** add the generated `tsv` column and index, a custom `BaseRetriever` running the hybrid SQL (vector plus keyword, fused by RRF), switchable by config, compared against baseline on the golden set.

**Verify first:** the generated column coexists with `PGVectorStore` inserts and reads.

**Done when:**
- Exact-term queries ("Neapolitan sixth", "Aliases like English horn") improve or stay equal compared with vector-only.
- A table of precision@5 and recall@5 for vector-only vs hybrid is saved.
- The decision on which mode is default is recorded in DECISIONS.md.

## Story 16: RAGAs evaluation

**Build:** run export script (question, answer, contexts, reference), `eval/` Python container with `run_ragas.py`, golden set of about 31 questions, results section in EVALUATION.md.

**Done when:**
- `docker compose run eval` prints all four RAGAs metrics.
- Results are compared to the targets (faithfulness 0.8 or above, context metrics 0.7 or above) and low cases are explained.
- Decision recorded on whether tool outputs count as contexts.
- Total evaluation spend is logged.

## Story 17: Final pass

**Build:** update all docs to match reality, a demo script (the questions to show, including the Convention-conflict and injection cases), a reflection section covering known problems and improvement ideas, a clean-clone setup check.

**Done when:**
- A fresh clone starts with `docker compose up` and the README steps.
- The demo script runs end to end.
- The reflection names real failure cases found during evaluation.

## Stretch (only if everything above is done)

`harmonic_series` tool, more Seed list pages, multi-model switching, Open Music Theory 2e if it becomes fetchable.
