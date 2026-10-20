# Glossary

Technical terms. Domain terms (Artist, Release, Edition, Discography, Seed list, Corpus, Citation, Disputed claim, Candidate, Conversation) are defined in [CONTEXT.md](../CONTEXT.md).

## RAG and retrieval

| Term | Meaning |
|---|---|
| RAG | Retrieval-augmented generation. Retrieve relevant text, give it to the LLM, generate an answer grounded in it. |
| Knowledge base | The stored, indexed corpus the bot retrieves from. |
| Chunk | A small piece of a document (here about 800 characters) that is embedded and retrieved. |
| Embedding | A vector of numbers representing the meaning of a text. Similar meanings give nearby vectors. |
| Vector database | A database that stores vectors and finds the nearest ones quickly (here Postgres with pgvector). |
| Cosine similarity | Similarity measured by the angle between two vectors. |
| Retriever | The LangChain interface that takes a query and returns documents. |
| BM25 | A keyword ranking algorithm. Good for exact names. |
| Hybrid search | Combining keyword (BM25) and vector search. |
| RRF | Reciprocal rank fusion. Merges ranked lists by summing 1/(k+rank). |
| Query translation | Rewriting the user's query before retrieval to retrieve better. |
| Multi-query | Rewriting one question into several variants and merging results. |
| Decomposition | Splitting a complex question into sub-questions. Here it happens through repeated tool calls. |
| Self-query / structured retrieval | Turning a question into metadata filters. Here done through typed tool arguments. |
| HyDE | Embedding a hypothetical answer instead of the question. Not used. |
| Metadata filter | A condition on chunk metadata (for example `entity_type = band`). |
| Citation | A reference from an answer to the chunk it came from. |
| Grounding | Keeping an answer supported by retrieved context. |
| Hallucination | A claim not supported by the context or reality. |

## LLM and agents

| Term | Meaning |
|---|---|
| Tool (function) calling | The model returns a structured request to run a function, the app runs it and returns the result. |
| `createAgent` | LangChain's helper that runs the tool loop and memory for you. |
| Checkpointer | Component that saves conversation state per `thread_id` (here `PostgresSaver`). |
| `thread_id` | Identifier of one conversation. |
| SSE | Server-Sent Events. One HTTP response kept open while the server sends messages. Not the same as SSR. |
| SSR | Server-side rendering. The server builds the page HTML. SvelteKit does this by default. |
| OpenRouter | A gateway exposing many models through an OpenAI-compatible API. |
| Prompt injection | Text that tries to override the model's instructions. |
| Indirect prompt injection | Injection hidden in retrieved documents or tool output instead of the user message. |
| Token | The unit of text models read and are billed for. |

## Evaluation

| Term | Meaning |
|---|---|
| Golden set | Hand-written questions with expected sources and answers. |
| precision@k | Share of the top k retrieved chunks that are relevant. |
| recall@k | Share of the relevant sources that appear in the top k. |
| RAGAs | Python library of RAG metrics using an LLM as judge. |
| Faithfulness | Share of answer claims supported by the retrieved context. |
| Answer relevancy | Whether the answer addresses the question. |
| Context precision | Whether retrieved context is relevant and ranked high. |
| Context recall | Whether retrieval captured the needed information. |
| Tool selection accuracy | Whether the agent called the right tool. |
| Parameter accuracy | Whether it passed the right arguments. |

## Metal terms used in the corpus

| Term | Meaning |
|---|---|
| Proto-metal | Late 1960s to early 1970s heavy rock that anticipated metal. |
| Heavy metal | Genre that emerged around 1970. Its first song is disputed. |
| NWOBHM | New Wave of British Heavy Metal, late 1970s to early 1980s. |
| Thrash metal | Fast, aggressive early 1980s style. |
| Death metal | Extreme style with growled vocals and complex riffs. |
| Black metal | Extreme style with shrieked vocals, tremolo riffs and lo-fi production. |
| Doom metal | Slow, heavy, downtuned style. |
| Power metal | Fast, melodic, fantasy-themed style. |
| Progressive metal | Metal with complex structures and long compositions. |
| Metalcore | Fusion of metal and hardcore punk. |
| Deathcore | Fusion of death metal and metalcore. |
| Studio album, EP, single, split | MusicBrainz release types the tools filter on. |
| MBID | MusicBrainz identifier for an artist, release or other entity. |
