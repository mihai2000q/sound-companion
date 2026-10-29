# Metal Archive Assistant

A domain-focused RAG chatbot for exploring metal artists and discographies, from proto-metal and heavy metal through thrash, death, black, doom, power, progressive, metalcore and deathcore.

Sprint 2 project: advanced RAG (query translation, structured retrieval, hybrid search), tool calling, a streaming SvelteKit UI, and an evaluation harness.

Example questions it should handle:

- "What was the first metal song ever?" (a disputed answer: the bot lists each candidate with its own citation)
- "Tell me about Opeth's early albums."
- "What did Metallica release between 1983 and 1991?" (MusicBrainz tool)
- "Compare the discographies of Slayer and Megadeth." (retrieval plus several tools)

## Status

Documentation phase complete. Implementation proceeds story by story, see [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md).

## Stack

| Layer | Choice |
|---|---|
| Frontend and server | SvelteKit (Svelte 5), TypeScript, Tailwind + shadcn/ui |
| Orchestration | LangChain.js (`createAgent`, retrievers, tools), PostgresSaver for memory |
| LLM and embeddings | OpenRouter (OpenAI-compatible) |
| Database | PostgreSQL with pgvector, in Docker |
| Evaluation | Deterministic metrics in TypeScript, RAGAs in a small Python container |

## Documents

| File | Purpose |
|---|---|
| [CONTEXT.md](CONTEXT.md) | Domain language (Artist, Release, Discography, Citation, ...) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, request flow, SSE events, folder layout |
| [docs/DOMAIN.md](docs/DOMAIN.md) | Corpus, seed list rules, sources, licensing, bot behaviour |
| [docs/DATABASE-SCHEMA.md](docs/DATABASE-SCHEMA.md) | Postgres tables, indexes, hybrid query |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | RAG, LangChain and metal terminology |
| [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md) | Ordered stories with acceptance criteria |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision log with reasons |
| [docs/EVALUATION.md](docs/EVALUATION.md) | Golden set, metrics, RAGAs setup |
| [docs/SECURITY.md](docs/SECURITY.md) | Threat model and defences |
| [docs/SVELTE-PRIMER.md](docs/SVELTE-PRIMER.md) | The Svelte 5 you need for this project |

## Budget

Target under 1 EUR of OpenRouter spend, hard stop at 4 EUR. Every request's tokens and cost are written to Postgres, and the app refuses requests once the hard cap is reached. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#cost-guard).

## Out of scope

Authentication, multi-language support, remote MCP tools, own MCP servers, public deployment.
