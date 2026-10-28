# Decision log

Each entry: decision, reason, and what would change it.

| # | Decision | Reason | Revisit if |
|---|---|---|---|
| 1 | SvelteKit (Svelte 5) + TypeScript | Author's preference, reviewer approved, one language. Course supports a JS track. | LangChain.js gaps cost too much time. Then Next.js (same server code) or Python backend. |
| 2 | RAG and tool logic isolated in `src/lib/server` | Keeps the UI shell swappable and the code testable from scripts. | Never. |
| 3 | Domain: metal artists and discographies | Author interest, checkable answers, natural tools (MusicBrainz), good test for hybrid search. | The seed list coverage spike fails (see 5). |
| 4 | Lyrics not used | Copyright and poor fit for factual questions. | Never. |
| 5 | Curated seed list (about 120 bands + about 40 genre/history articles) | `music-wiki` has no genre column. A list gives control, a bounded cost and a ready golden set. | Snapshot coverage is too low, then fill more from the Wikipedia API. |
| 6 | Source: `music-wiki` snapshot plus API gap filling | Static, MIT licensed, reproducible. Live fetching is a stretch. | Snapshot text per artist is too thin. |
| 7 | Encyclopaedia Metallum not scraped | Terms unchecked, no free dump found. | Terms confirm scraping is allowed. |
| 8 | pgvector in the app's Postgres, behind a `Retriever` interface | One database, one backup, SQL metadata filters, transactional deletes, hybrid in one query. SRP is satisfied by the interface, not by splitting databases. | Scale or a team owning search. Chroma or another store becomes a second adapter. |
| 9 | Cosmos DB rejected | Second database and Azure dependency for no needed feature. | An Azure requirement appears. |
| 10 | Built-in LangChain retrievers first, custom SQL as fallback | Less code, course-aligned. The range-filter argument for custom SQL was dropped because years live in tools, not chunks. | Built-in hybrid is unavailable or awkward. |
| 11 | No years in chunks | Avoids stale or contradictory dates, structured facts come from MusicBrainz. | Never. |
| 12 | Section-aware chunking, about 800 chars, 100 overlap | Keeps topics (early years vs lineup) separate. | Retrieval eval shows poor recall. |
| 13 | `createAgent` with retrieval as a tool, no router | Matches the course, less code, decomposition comes free through the tool loop. Carries to Sprint 3. | Cost or latency of agent loops is too high. |
| 14 | PostgresSaver for memory | Course pattern, uses the existing database. | API mismatch in JS. Fall back to MemorySaver plus own `messages` table. |
| 15 | Query translation: multi-query, decomposition (via loop), structured args. No HyDE or step-back. | Fits the use cases and the budget. | Eval shows recall problems HyDE might fix. |
| 16 | Four tools: knowledge base search, MusicBrainz lookup, stats, compare | At least 3 required, tools are deterministic and testable. | Time pressure: drop `compare_discographies`. |
| 17 | Hand-rolled SSE with typed events | The event stream is the shared contract for UI, logging and the RAG-process view. | Never. |
| 18 | shadcn/ui on Tailwind | Ready components (`collapsible`, `progress`). Check version compatibility at setup. | Tailwind 4 compatibility issues. |
| 19 | Chat + inspector panel UI | Satisfies "show context, sources and tool results" and gives the RAG-process view cheaply. | Never. |
| 20 | OpenRouter for chat and embeddings, two chat models | Required by the brief. Cheap model for rewriting, stronger one for answers. | Embedding endpoint or model unavailable. Use local embeddings. |
| 21 | Budget guard at 1 EUR soft, 4 EUR hard | Keeps total under the 5 EUR limit, reuses the cost-display data. | Never. |
| 22 | Disputed facts are presented side by side | Matches real debate, easier to verify, clear faithfulness test. | Never. |
| 23 | Answer only from retrieved context | Keeps RAGAs faithfulness meaningful and avoids unsourced claims. | Eval shows too many "I don't know" answers for covered topics. |
| 24 | Optional tasks: injection protection, cost display, logging (medium), RAGAs, hybrid (hard), citations, history and export (easy), RAG-process view (stretch) | Exceeds the minimum of 2 medium and 1 hard. | Time pressure: drop the stretch, then logging. |
| 25 | Evaluation in three layers | Two are free and run on every change, only RAGAs spends budget. | Never. |
| 26 | RAGAs in a Python container over exported JSON | RAGAs is Python only. The course recommends this approach for TypeScript students. | Python tooling becomes painful. Write the metrics as TypeScript judge prompts. |
| 27 | No auth, single local user, English only | Out of scope for the brief and the budget. | Never for this sprint. |
| 28 | Plain SQL migrations, no ORM | Few tables, SQL is the point (hybrid query, usage sums). | Schema grows. |
| 29 | Work in stories, not days | The author wants feature-by-feature implementation. | Never. |
| 30 | "Artist" (group or person) replaces "band"; `entity_type` is `artist`, `genre`, `history` | Metal includes solo artists and MusicBrainz models both as artists. | Never. |
| 31 | "Release" means a MusicBrainz release group, "Edition" a release. Discography defaults to studio albums and EPs. | Counting editions would list one album many times. | The user asks for other types (supported by `release_types`). |
| 32 | Subgenre tags are per Artist, multi-valued, from the seed list only | Per-release tagging is out of scope and a bot-invented tag would have no Citation. | Never. |
| 33 | Disputed claims are detected by retrieved disagreement and by a `contested` flag in the seed list | The model catches disagreement, the flag makes the golden set deterministic. | Never. |
| 34 | `CONTEXT.md` holds domain terms only, `GLOSSARY.md` holds technical terms. "Source" is split into Provenance and Citation. | One word for two things caused ambiguity in the docs and the schema. | Never. |

## Open facts (verify in the story that needs them)

- `music-wiki` coverage of the seed list (story 2).
- `@langchain/pgvector` hybrid API, `EnsembleRetriever` and `BM25Retriever` availability (story 15).
- PostgresSaver JS API and state access for export (stories 5 and 14).
- OpenRouter model IDs, tool-calling support, prices, embedding model and dimension (story 1 and 3).
- Tailwind and shadcn/ui version compatibility (story 1).
- Licensing of Wikipedia text and the dataset, MusicBrainz terms (story 2).
