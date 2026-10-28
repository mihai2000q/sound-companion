# Sound Companion

A study companion for music theory and musical instruments. Ask what a chord is, how a clarinet transposes, why the 7th harmonic sounds flat, or how two textbooks name the same note differently. The bot answers from a curated, cited corpus and calls local tools for the calculations.

Sprint 2 project: advanced RAG (query translation, structured retrieval, hybrid search), tool calling, a streaming React UI, and an evaluation harness.

Example questions:

- "What is the circle of fifths and how does it relate to key signatures?" (retrieval)
- "Which chord is made of D, F, A and C?" (tool, ambiguous: Dm7 or F6/D)
- "What does a B-flat clarinet sound when it reads a written C?" (tool plus retrieval)
- "In the key of C, what is middle C called, and what do German speakers call B?" (convention conflict, two cited conventions)
- "How do the viola and the violin differ in size, tuning and role?" (comparison)

## Status

Stories 1 to 16 are done: ingestion and indexing, retrieval (vector and hybrid), the agent with its music tools, the streaming UI with Citations and an inspector, the usage and budget guard, logging and monitoring, prompt-injection defences, conversation history, and the evaluation harness (retrieval metrics, tool-calling, injection tests, RAGAs). Story 17 (final pass) is in progress. See [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md).

History: the project first targeted metal artists ([docs/archive/metal/](docs/archive/metal/)), then music theory and instruments on a SvelteKit and TypeScript stack ([docs/archive/typescript-stack/](docs/archive/typescript-stack/)). Both were changed after research, see decisions 1 to 5 in [docs/DECISIONS.md](docs/DECISIONS.md).

## Stack

| Layer | Choice |
|---|---|
| Frontend | React (Vite, TypeScript), Tailwind + DaisyUI |
| Backend | Python 3.12, FastAPI, LangChain (`create_agent`), `langchain-postgres` `PGVectorStore`, LangGraph Postgres checkpointer |
| Music computation | `pychord` (chords), `music21` (scales, intervals, keys), small hand-written functions |
| LLM and embeddings | OpenRouter (OpenAI-compatible) |
| Database | PostgreSQL with pgvector, in Docker. SQLAlchemy models and Alembic migrations |
| Evaluation | Deterministic metrics, RAGAs (same Python project) |

## Running locally

1. Copy `.env.example` to `.env` and change the placeholder password if you like.
2. Put your OpenRouter key in your shell environment (it is not read from `.env`): `export OPENROUTER_API_KEY=...`
3. `docker compose up --build` starts Postgres (pgvector, named volume `pgdata`), the server and the client dev server. The server applies the database migrations on startup and creates an empty `chunks` table, so it starts before anything is indexed. Rebuild (`--build`) after pulling new migrations, because the image holds them.
4. Build the Corpus and the index (next section). Until then the chat answers from an empty knowledge base.

| Service | URL |
|---|---|
| Client | http://localhost:7003 (`/` chat, `/monitoring` latency, errors and tool calls, `/health` server and database status) |
| Server | http://localhost:7002 (`POST /api/chat`, `GET /api/health`, `/api/monitoring`, `/api/threads`) |
| Postgres | `localhost:7001` |

Ports come from `.env`. To run the migrations by hand, see [Migrations](docs/DATABASE-SCHEMA.md#migrations).

### Building the Corpus

With the stack up, from `sound-companion.server` (needs [uv](https://docs.astral.sh/uv/) and Python 3.12; `uv run` installs the dependencies, the `ragas` group is not needed). The host reaches Postgres on `POSTGRES_PORT` from `.env`. Checked on a fresh clone: the whole path takes about 3 minutes for ingest and 3.5 minutes for indexing, and indexing costs about 0.02 credits.

```
uv run python -m scripts.ingest              # fetch, clean, report and store
uv run python -m scripts.ingest --dry-run    # the same, but store nothing
```

The script reads `data/seed-list.json`, fetches the Wikipedia pages at about 1 request per second and clones Open Music Theory v1 into `data/cache/` (not committed). Re-running uses the cache and makes no requests. It prints which entries were included, dropped below the 5,000-character floor or flagged, and which Open Music Theory files were excluded.

Then create the HNSW index, chunk and embed the documents (about 0.02 credits, 3 to 4 minutes), from the same folder:

```
uv run python -m scripts.setup_chunks        # chunks table (if missing) and HNSW index, safe to repeat
uv run python -m scripts.index               # chunk, embed, upsert, delete stale chunks
```

Then open the client and ask a question: it answers with Citations (a chat turn costs about 0.001 credits). `RETRIEVER_MODE=vector|hybrid` in `.env` picks the retriever (default `vector`). The evaluation commands are listed in [docs/EVALUATION.md](docs/EVALUATION.md) and `CLAUDE.md`.

## Documents

| File | Purpose |
|---|---|
| [CONTEXT.md](CONTEXT.md) | Domain language (Note, Sounding pitch, Convention, Citation, ...) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, request flow, SSE events, folder layout |
| [docs/DOMAIN.md](docs/DOMAIN.md) | Corpus, seed list rules, sources, licensing, bot behaviour, tools |
| [docs/DATABASE-SCHEMA.md](docs/DATABASE-SCHEMA.md) | Postgres tables, indexes, hybrid query |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | Technical terms (RAG, RRF, SSE, ...) |
| [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md) | Ordered stories with acceptance criteria |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision log with reasons |
| [docs/DEMO.md](docs/DEMO.md) | Demo script: questions to show, checks to run, known weak spots |
| [docs/EVALUATION.md](docs/EVALUATION.md) | Golden set, metrics, RAGAs setup |
| [docs/REFLECTION.md](docs/REFLECTION.md) | Known problems with evidence, ranked improvement ideas |
| [docs/SECURITY.md](docs/SECURITY.md) | Threat model and defences |
| [docs/research/](docs/research/) | Verified facts about data sources, libraries and APIs |

## Budget

Target under 1 credit of OpenRouter spend, hard stop at 4 credits (credits are treated as USD, verify on the account page). Every model call's tokens and cost are written to Postgres, and the app refuses requests once the hard cap is reached. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#cost-guard).

## Out of scope

Authentication, multi-language support, audio input (recording or analysing sound), YouTube links, remote MCP tools, own MCP servers, public deployment.
