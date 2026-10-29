# Decision log

Each entry: decision, reason, and what would change it. Entries 1 to 4 are about the subject change. The old metal log is in [archive/metal/DECISIONS.md](archive/metal/DECISIONS.md).

| # | Decision | Reason | Revisit if |
|---|---|---|---|
| 1 | Subject changed from metal artists to music theory and instruments | Research showed the metal corpus was patchy (six headline bands had no page in the `music-wiki` snapshot, no free metal dataset, no permission found for Encyclopaedia Metallum). The new corpus was measured before design. | Never. |
| 2 | Data was verified before design this time | The metal subject failed on data. Two research agents checked licences, fetchability and tools first. | Never. |
| 3 | Audio input (recording, analysis, YouTube links) is out of scope | Audio analysis is a separate signal-processing problem, accuracy on real songs is weak, and YouTube downloads breach its terms. | A later project. |
| 4 | Scope: music theory and instruments together | A question like "what does a B-flat clarinet sound when it reads a written C" needs both the corpus and a tool. | Never. |
| 5 | Stack: SvelteKit (Svelte 5), TypeScript, LangChain.js, shadcn/ui | Author's preference, reviewer approved, one language. Course supports a JS track. | LangChain.js gaps cost too much time. Then Next.js (same server code). |
| 6 | RAG and tool logic isolated in `src/lib/server` | Keeps the UI shell swappable and the code testable from scripts. | Never. |
| 7 | Audience: a learner, beginner to intermediate | Tightens the system prompt and the golden set. | Never. |
| 8 | Corpus: about 150 Wikipedia articles plus Open Music Theory v1 | Both CC BY-SA 4.0, structured headings, enough size (about 2,000 to 5,000 chunks), and the two sources use different Conventions. | OMT 2e becomes fetchable, or a text gap appears. |
| 9 | Not used: Wikibooks, LibreTexts books, Open Opus, Met Museum | Wikibooks is thin, LibreTexts licences are mixed (NC, GFDL) with a 5 s crawl delay, Open Opus has no SLA, the Met API has no prose. | A gap in the golden set that these would fill. |
| 10 | Wikipedia pages fetched from the REST HTML endpoint | It keeps headings and tables, `explaintext` flattens or drops them, and the research verified headings in the response. | Table extraction fails for the transposition tables. |
| 11 | Ingestion at about 1 request per second with a User-Agent, one-off script with caching | Wikipedia rate-limited a burst in the research. | Never. |
| 12 | 5,000-character floor for Wikipedia pages | 28 of 190 Hornbostel-Sachs links were stubs under 2,000 characters. | The floor drops needed pages. |
| 13 | Redirects resolved, old names stored as Aliases and prepended to chunk text | Makes "English horn" find "Cor anglais" in vector and keyword search. | Never. |
| 14 | Store `revision_id` and `license` per document, show attribution links | CC BY-SA requires attribution, and pages change daily. | Never. |
| 15 | pgvector in the app's Postgres, behind a `Retriever` interface | One database, SQL filters, transactional deletes, hybrid in one query. SRP is satisfied by the interface, not by splitting databases. | Scale, or a reviewer expectation of Chroma. |
| 16 | `PGVectorStore` for core retrieval, custom SQL hybrid retriever for the hard task only | Matches the course pattern with the least code. The JS package has no hybrid search. Custom work stays in the one place the package cannot do it. | `PGVectorStore` layout blocks needed metadata. |
| 17 | Chunk table in the layout `PGVectorStore` expects; `document_id` stored in `metadata` | The store never writes a separate column. | The store changes its layout. |
| 18 | Section-aware chunking from real headings (HTML sections, OMT `##` and `###`), about 800 characters, 100 overlap | Keeps topics separate and gives Citations a section. | Retrieval eval shows poor recall. |
| 19 | `createAgent` with retrieval as a tool, no router | Matches the course, less code, decomposition comes free through the tool loop. | Agent loops cost too much. |
| 20 | `PostgresSaver` for memory, `getState` for export | Course pattern and the JS API exists (per the research, to be tested against a database in story 5). | API mismatch at runtime. Fall back to `MemorySaver` plus own `messages` table. |
| 21 | Query translation: multi-query inside the retrieval tool, decomposition via the tool loop, structured args. No HyDE or step-back. | Fits the use cases and the budget. | Eval shows recall problems HyDE might fix. |
| 22 | Six tools: knowledge base search plus `chord_info`, `scale_info`, `interval_between`, `transpose_for_instrument`, `note_frequency` | At least 3 required, all deterministic and testable. `harmonic_series` is a stretch. | Time pressure: drop `scale_info`. |
| 23 | `tonal` (MIT) as the music engine, hand-written maths for frequency and cents | Local, no key, 15 sample calls verified. It has no instrument data and rejects `H4`. | Package problems. |
| 24 | Transposition table of about 14 instruments, each with a Citation | `tonal` has no instrument data, and a cited table ties the tool to the Corpus. | Never. |
| 25 | Tools use scientific pitch notation (C4 = middle C, A4 = 440 Hz) and state it | Sources disagree on conventions. Stating the tool's Convention stops silent contradictions. | Never. |
| 26 | Convention conflicts are shown side by side with a Citation each, no winner | Matches how sources actually differ, easier to verify, clear faithfulness test. | Never. |
| 27 | Ambiguous analyses return all Candidates | `Chord.detect` gives Dm7 and F6/D for D, F, A, C. | Never. |
| 28 | Answer only from retrieved context and tool results | Keeps RAGAs faithfulness meaningful. | Eval shows too many "I don't know" answers for covered topics. |
| 29 | Hand-rolled SSE with typed events | The event stream is the shared contract for UI, logging and the RAG-process view. | Never. |
| 30 | Chat plus inspector panel UI | Shows context, sources and tool results, gives the RAG-process view cheaply. | Never. |
| 31 | OpenRouter for chat and embeddings: `openai/text-embedding-3-small` (1536 dimensions), `openai/gpt-4o-mini` first for answers and rewriting | The research tested them end to end. Cheaper models are compared with the tool-calling eval. | A cheaper model passes the eval, or a guardrail blocks a model. |
| 32 | Budget in OpenRouter credits (soft 1, hard 4), treated as USD | `usage.cost` is returned in credits on every response, no price table needed. | The account page shows another relation. |
| 33 | Persistence: Postgres only, plain SQL migrations, no ORM | Few tables, SQL is the point (hybrid query, usage sums). | Schema grows. |
| 34 | Optional tasks: injection protection, cost display, logging (medium), RAGAs, hybrid (hard), citations, history and export (easy), RAG-process view (stretch) | Exceeds the minimum of 2 medium and 1 hard. | Time pressure: drop the stretch, then logging. |
| 35 | Evaluation in three layers | Two are free and run on every change, only RAGAs spends budget. | Never. |
| 36 | RAGAs in a Python container over exported JSON | RAGAs is Python only, and the course recommends this for TypeScript students. | Python tooling becomes painful. Write the metrics as TypeScript judge prompts. |
| 37 | No auth, single local user, English only | Out of scope for the brief and the budget. | Never for this sprint. |
| 38 | `CONTEXT.md` holds domain terms, `GLOSSARY.md` holds technical terms | One glossary for each kind of language. | Never. |
| 39 | Work in stories, not days | The author wants feature-by-feature implementation. | Never. |
| 40 | Stay on TypeScript for the backend, keep `PGVectorStore` for storage and dense retrieval | A spike ran it on Postgres with 3,000 chunks: filters, retriever, MMR, deletes and the generated `tsvector` column all worked. The workarounds are small. Python would add a second codebase and lose the verified `tonal` tools. | The spike's untested areas fail (TypeScript compilation, real embeddings, concurrent writers), or Sprint 3 is Python-only. |
| 41 | Own the DDL and HNSW index in a migration, ingest by delete-by-`document_id` then add in one transaction, guard filters | The store has no index creation, no upsert, and an empty filter deletes everything. | The store adds upsert and safer deletes. |

## Open facts (verify in the story that needs them)

- Table extraction from the REST HTML for the "Transposing instrument" article and any tuning tables (story 2).
- Wikipedia API rate-limit policy page was not read (story 2).
- OMT v1 repo has no LICENSE file. The licence is declared in the page footer and about page (story 2).
- `PGVectorStore` was spiked (column mapping and coexistence with a generated `tsv` column confirmed). Still untested: TypeScript compilation, real embeddings, tables above 3,000 rows, concurrent writers, and `hnsw.iterative_scan` through the store (stories 3 and 4).
- `PostgresSaver` against a real database, and `getState` for export (stories 5 and 14).
- Exact stream-mode mapping for `citations` and `queries` events (story 6).
- Credits equal USD on this OpenRouter account, and workspace guardrails for the chosen models (stories 1 and 11).
- A Tailwind 4, shadcn/ui and SvelteKit 3 build (story 1, the research did not run one).
