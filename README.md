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

Documentation phase. Implementation proceeds story by story, see [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md).

History: the project first targeted metal artists ([docs/archive/metal/](docs/archive/metal/)), then music theory and instruments on a SvelteKit and TypeScript stack ([docs/archive/typescript-stack/](docs/archive/typescript-stack/)). Both were changed after research, see decisions 1 to 5 in [docs/DECISIONS.md](docs/DECISIONS.md).

## Stack

| Layer | Choice |
|---|---|
| Frontend | React (Vite, TypeScript), Tailwind + DaisyUI |
| Backend | Python 3.12, FastAPI, LangChain (`create_agent`), `langchain-postgres` `PGVectorStore`, LangGraph Postgres checkpointer |
| Music computation | `pychord` (chords), `music21` (scales, intervals, keys), small hand-written functions |
| LLM and embeddings | OpenRouter (OpenAI-compatible) |
| Database | PostgreSQL with pgvector, in Docker |
| Evaluation | Deterministic metrics, RAGAs (same Python project) |

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
| [docs/EVALUATION.md](docs/EVALUATION.md) | Golden set, metrics, RAGAs setup |
| [docs/SECURITY.md](docs/SECURITY.md) | Threat model and defences |
| [docs/REACT-PRIMER.md](docs/REACT-PRIMER.md) | The React and SSE patterns this project uses |
| [docs/research/](docs/research/) | Verified facts about data sources, libraries and APIs |

## Budget

Target under 1 credit of OpenRouter spend, hard stop at 4 credits (credits are treated as USD, verify on the account page). Every model call's tokens and cost are written to Postgres, and the app refuses requests once the hard cap is reached. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#cost-guard).

## Out of scope

Authentication, multi-language support, audio input (recording or analysing sound), YouTube links, remote MCP tools, own MCP servers, public deployment.
