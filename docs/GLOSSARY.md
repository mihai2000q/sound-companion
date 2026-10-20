# Glossary

Technical terms. Domain terms (Note, Pitch class, Written pitch, Sounding pitch, Chord, Chord symbol, Instrument, Alias, Convention, Convention conflict, Candidate, Source type, Seed list, Corpus, Provenance, Citation, Conversation) are defined in [CONTEXT.md](../CONTEXT.md).

## RAG and retrieval

| Term | Meaning |
|---|---|
| RAG | Retrieval-augmented generation. Retrieve relevant text, give it to the LLM, generate an answer grounded in it. |
| Knowledge base | The stored, indexed text the bot retrieves from (the Corpus plus its index). |
| Chunk | A small piece of a document (here about 800 characters) that is embedded and retrieved. |
| Embedding | A vector of numbers representing the meaning of a text. Similar meanings give nearby vectors. |
| Vector database | A database that stores vectors and finds the nearest ones quickly (here Postgres with pgvector). |
| Cosine similarity | Similarity measured by the angle between two vectors. |
| HNSW | An approximate nearest-neighbour index used by pgvector for fast search. |
| Retriever | The LangChain interface that takes a query and returns documents. |
| `PGVectorStore` | LangChain class (`langchain-postgres`, v2 API) that stores and searches chunks in Postgres. |
| BM25 | A keyword ranking algorithm. Good for exact terms. |
| Hybrid search | Combining keyword and vector search. |
| RRF | Reciprocal rank fusion. Merges ranked lists by summing 1/(k+rank). |
| Query translation | Rewriting the user's query before retrieval to retrieve better. |
| Multi-query | Rewriting one question into several variants and merging results. |
| Decomposition | Splitting a complex question into sub-questions. Here it happens through repeated tool calls. |
| Structured retrieval | Turning a question into metadata filters. Here done through typed tool arguments. |
| HyDE | Embedding a hypothetical answer instead of the question. Not used. |
| Metadata filter | A condition on chunk metadata (for example `source_type = textbook`). |
| Grounding | Keeping an answer supported by retrieved context. |
| Hallucination | A claim not supported by the context or reality. |
| Revision id | The version of a Wikipedia page that was fetched, kept for Provenance. |

## LLM and agents

| Term | Meaning |
|---|---|
| Tool (function) calling | The model returns a structured request to run a function, the app runs it and returns the result. |
| `create_agent` | LangChain's helper that runs the tool loop and memory for you. |
| Checkpointer | Component that saves conversation state per `thread_id` (here `AsyncPostgresSaver`). |
| `thread_id` | Technical identifier of one Conversation. |
| `pychord` | Python library for chords: components, names, transposition, detecting a chord from notes. |
| `music21` | Python music analysis toolkit, used for scales, intervals and key signatures. |
| FastAPI | Python web framework used for the backend API and the SSE stream. |
| Vite | Frontend build tool and dev server for the React app, proxies `/api` to the backend in development. |
| SSE | Server-Sent Events. One HTTP response kept open while the server sends messages. Not the same as SSR. |
| SSR | Server-side rendering. The server builds the page HTML. Frameworks like Next.js do this by default, our React single-page app does not. |
| OpenRouter | A gateway exposing many models through an OpenAI-compatible API. |
| Credits | OpenRouter's billing unit. `usage.cost` is reported in credits, treated here as USD. |
| Prompt injection | Text that tries to override the model's instructions. |
| Indirect prompt injection | Injection hidden in retrieved documents or tool output instead of the user message. |
| Token | The unit of text models read and are billed for. |

## Evaluation

| Term | Meaning |
|---|---|
| Golden set | Hand-written questions with expected sources and answers. |
| precision@k | Share of the top k retrieved chunks that are relevant. |
| recall@k | Share of the relevant pages that appear in the top k. |
| RAGAs | Python library of RAG metrics using an LLM as judge. |
| Faithfulness | Share of answer claims supported by the retrieved context. |
| Answer relevancy | Whether the answer addresses the question. |
| Context precision | Whether retrieved context is relevant and ranked high. |
| Context recall | Whether retrieval captured the needed information. |
| Tool selection accuracy | Whether the agent called the right tool. |
| Parameter accuracy | Whether it passed the right arguments. |

## Licensing

| Term | Meaning |
|---|---|
| CC BY-SA 4.0 | Creative Commons licence requiring attribution and the same licence for derivatives. Applies to Wikipedia and Open Music Theory. |
| Attribution | Crediting the source, by link, as the licence requires. |
