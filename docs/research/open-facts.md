# Open facts: verification report

> **Status note:** this report was written for the abandoned metal subject. Sections 2 to 5 (LangChain.js, PostgresSaver and streaming, OpenRouter, Tailwind and DaisyUI) and the Wikipedia and MusicBrainz parts of section 6 still apply to Sound Companion. Sections 1 and 7 (the `music-wiki` dataset and MusicBrainz release groups) and the Encyclopaedia Metallum part of section 6 are archived context only. Current subject research: [music-theory-data.md](music-theory-data.md) and [instruments-data.md](instruments-data.md).

Date of research: 2026-10-19. Only primary sources were used: the Hugging Face dataset files and card, package source code installed from npm (read in a scratch directory), first-party API responses (OpenRouter, MusicBrainz), and official documentation or licence pages. "Verified" means checked against such a source today. Anything else is marked "unverified". Prices and model lists change daily, so re-check them when you implement the story.

## Summary

| # | Item | Verdict | Impact on our docs |
|---|---|---|---|
| 1 | `music-wiki` coverage and licence | Verified (measured on the parquet files, except the `musicbrainz_release` split, which was not downloaded) | High. The core band pages for Black Sabbath, Judas Priest, Metallica, Megadeth, Opeth, Deep Purple and Led Zeppelin are missing from the Wikipedia split. "MIT licensed" is incomplete: the text is Wikipedia text under CC BY-SA. |
| 2 | LangChain.js v1: `createAgent`, retrievers, `PGVectorStore` | Verified from installed source and the type definitions | High. There is no hybrid search in `@langchain/pgvector`. `BM25Retriever` is in-memory and lives in a deprecated package. The table layout in `DATABASE-SCHEMA.md` does not fit `PGVectorStore`. |
| 3 | `PostgresSaver`, state export, streaming | Verified (docs plus a live run of `createAgent` with `MemorySaver`; `PostgresSaver` itself read from source, not run against a database) | Medium. No API mismatch, so the fallback in decision 14 is not needed. SSE mapping is now known. |
| 4 | OpenRouter models, embeddings, usage | Verified (live API calls with the project key) | Medium. Embedding model and dimension can be fixed. Cost is reported in "credits", not EUR. |
| 5 | Tailwind 4 and DaisyUI 5 | Verified (official install pages and npm metadata) | Low to medium. Install steps differ from Tailwind 3 habits. SvelteKit 3 needs Node 22.17+ and Vite 8. |
| 6 | Licences and terms | Partly. Wikimedia and MusicBrainz verified. Encyclopaedia Metallum: no scraping clause found on reachable pages, no content licence found. | Medium. The reason for not scraping Metallum should change. Dataset licence statement needs fixing. |
| 7 | MusicBrainz v2 request shapes | Verified with live requests for Metallica | Medium. "Studio album" needs a client-side filter on `secondary-types`. About 10 pages for Metallica. |

---

## 1. `seungheondoh/music-wiki`

Method: downloaded the parquet shards for `wikipedia_music` (2 files), `musicbrainz_artist`, `musicbrainz_release_group` and `musicbrainz_genre` and queried them with DuckDB. The `musicbrainz_release` split (4 shards, 163k rows, album-level pages) was not downloaded, so album-level coverage is not measured. Shard URLs: `https://huggingface.co/datasets/seungheondoh/music-wiki/resolve/main/data/<file>.parquet` (file list from `https://huggingface.co/api/datasets/seungheondoh/music-wiki`).

### Dataset facts

- Columns are exactly `mbid`, `entity`, `text`, `url`, `entity_type`. Source: parquet schema read with DuckDB (`describe`).
- Split sizes (card): wikipedia_music 167890, musicbrainz_genre 1459, instrument 872, artist 7002, release 163068, release_group 15942, label 158, work 4282, series 12, place 49, event 16, area 360. Total is about 361k. Source: `https://huggingface.co/datasets/seungheondoh/music-wiki/raw/main/README.md`.
- `entity_type` values seen: `wiki_ontology` (all of `wikipedia_music`), `artist`, `release_group`, `genre`. Verified in the loaded files.
- `wikipedia_music` rows have an empty `mbid`. Verified.
- Genre pages appear in two places: in `wikipedia_music` and in `musicbrainz_genre` (with an `mbid`, often several MBIDs for one page, so the same text is duplicated). Verified for "Black metal" (3 genre rows plus 2 wiki rows).
- Some entries are misfiled: the band page "Led Zeppelin" and the genre article "Heavy metal music" are in the `musicbrainz_release_group` split, with `entity_type = release_group`. Verified. So lookups must search all splits by `url`, not one split by `entity_type`.
- The data is from 2023 (last modified 2023-08-19), so it is a snapshot. Source: HF API, `lastModified`.

### Seed-list probe

Exact match on `entity` (case-insensitive) unless noted. Length is characters of `text`.

| Requested | Result | Text length | Notes |
|---|---|---|---|
| Black Sabbath | MISSING as a band page | n/a | Only albums, songs, "List of Black Sabbath and Heaven & Hell members" (12812 chars, starts with a band summary) |
| Led Zeppelin | Found, in the `musicbrainz_release_group` split | 47021 | Band summary plus history |
| Deep Purple | MISSING as a band page | n/a | "List of Deep Purple members" (6632), album "Deep Purple in Rock" (15957) |
| Blue Cheer | Found (`wikipedia_music`) | 14604 | |
| Iron Butterfly | Found | 19373 | |
| Steppenwolf | Found as "Steppenwolf (band)" | 14708 | Exact name "Steppenwolf" missing |
| Judas Priest | MISSING as a band page | n/a | "List of Judas Priest band members" (2897) and albums |
| Metallica | MISSING as a band page | n/a | Albums, songs, "List of Metallica concert tours" (3069), awards list (9050) |
| Slayer | Found in `musicbrainz_artist` | 49694 | Not in `wikipedia_music` under that name |
| Megadeth | MISSING as a band page | n/a | Members list (5140), awards (3552), albums |
| Opeth | MISSING as a band page | n/a | Members list (3730), albums |
| Mgła | Found (`wikipedia_music`) | 4017 | "Mgla" without the diacritic is not found. Match on `url`, not on a folded name |
| Bring Me the Horizon | Found | 34728 | |
| Whitechapel | Found as "Whitechapel (band)" | 12448 | Also in `musicbrainz_artist` |
| Heavy metal music | Found only in `musicbrainz_release_group` split | 74792 | Not in `wikipedia_music` |
| History of heavy metal | MISSING | n/a | No entity or url match |
| Thrash metal | Found | 31022 | Also in the genre split |
| Black metal | Found | 63065 | |
| Deathcore | Found | 10848 | |
| Metalcore | Found | 17769 | |

Result for the 14 bands: 8 have a usable band page (Led Zeppelin, Blue Cheer, Iron Butterfly, Steppenwolf, Slayer, Mgła, Bring Me the Horizon, Whitechapel). 6 do not (Black Sabbath, Deep Purple, Judas Priest, Metallica, Megadeth, Opeth). Four of those six are the most famous metal bands in the list. For the 6 genre articles, 5 of 6 are present (only "History of heavy metal" is missing). Other genre pages present: Death metal (23491), Doom metal (17712), Power metal (13387).

Broad estimate: 7077 distinct URLs across `wikipedia_music`, `musicbrainz_artist` and `musicbrainz_release_group` mention "metal band" or "metal group" in their text. That is every kind of page (albums, lists, songs), not just bands. Only 219 of the 7002 `musicbrainz_artist` rows mention a metal band. So coverage of well-known metal bands is partial and has surprising holes, and a seed list of about 120 bands will need Wikipedia API gap filling for a meaningful share. Missing top-tier pages also often have a "List of X members" page whose first paragraph is a band summary, but that is not a substitute for the band article.

### Text structure

- Plain text with newlines. No Markdown or wiki markup. Example start of Mgła: `Mgła ([mɡwa]; English: "Fog") is a Polish black metal band ...\n\nHistory\nInitially founded as ...`.
- Section headings are kept as bare lines (`History`, `Discography`, `Studio albums`, `Personnel`, `References`, `External links`), with no marker, no level, and no blank line after them. Sub-headings (`Studio albums`, `EPs`) look the same as top headings. A heading has to be detected by heuristics (short line, no final period, preceded by a blank line or by a list). Verified on Mgła and Slayer.
- Lead paragraph is first, followed by a blank line.
- Tables are flattened to lines (e.g. `Groza (2008)`). Reference and "External links" sections are included as noise at the end.
- Text length varies hugely: 13713 of 167890 `wikipedia_music` rows are under 300 characters (category pages like "Category:Opeth members", 46 chars). Median length of rows mentioning "metal band" is 1936 characters, mean 4725.

### Licence

- Card header: `license: mit`. The card text does not mention Wikipedia's licence at all. Source: `https://huggingface.co/datasets/seungheondoh/music-wiki/raw/main/README.md`.
- The card says the pages are crawled from Wikipedia (seed page graph and the Wikipedia API) and from MusicBrainz entities. So the MIT label cannot cover the Wikipedia text, which stays under CC BY-SA 4.0 and GFDL (see item 6). The GitHub repo `seungheondoh/music-wiki` returned no licence or README at the main branch (HTTP 404 for the README, no licence field), so I could not find any further statement. Treat "MIT" as applying to the dataset's own packaging only. This is my reading of the sources, not a statement the dataset author makes.

---

## 2. LangChain.js (v1)

Installed in a scratch directory and read from source. Versions on npm today: `langchain` 1.5.18, `@langchain/core` 1.2.18, `@langchain/langgraph` 1.5.1, `@langchain/langgraph-checkpoint-postgres` 1.1.0, `@langchain/pgvector` 0.1.0, `@langchain/classic` 1.0.53, `@langchain/community` 1.1.29 (deprecated), `@langchain/openai` 1.6.2 (`npm view`).

### createAgent

- `import { createAgent, tool } from "langchain";` Verified: `createAgent` is exported from `langchain` 1.5.18 (`dist/index.d.ts`), and used in the official streaming docs at `https://docs.langchain.com/oss/javascript/langchain/streaming`.
- Options used: `model`, `tools`, `checkpointer` (docs example: `createAgent({ model, tools: [getWeather], checkpointer: new MemorySaver() })`). I ran this against OpenRouter and it worked (see item 4). Source: same docs page plus my run.

### Retrievers

| Class | Exists | Package and import | Notes |
|---|---|---|---|
| `EnsembleRetriever` | Yes | `@langchain/classic`: `import { EnsembleRetriever } from "@langchain/classic/retrievers/ensemble"` | Options `retrievers`, `weights` (default equal), `c` (default 60). Weighted reciprocal rank fusion. De-duplicates by `pageContent`. Source: `dist/retrievers/ensemble.js` |
| `MultiQueryRetriever` | Yes | `@langchain/classic`: `import { MultiQueryRetriever } from "@langchain/classic/retrievers/multi_query"` | `MultiQueryRetriever.fromLLM({ llm, retriever, queryCount?, prompt? })`. Source: `dist/retrievers/multi_query.d.ts`. We do our own rewrite inside the tool, so we do not need it |
| `BM25Retriever` | Yes, but only in a deprecated package | `@langchain/community`: `import { BM25Retriever } from "@langchain/community/retrievers/bm25"` | `BM25Retriever.fromDocuments(docs, { k })`. It keeps all documents in memory and scores them in JS (vendored BM25 from `@furkantoprak/bm25`). It does not talk to Postgres. `npm view @langchain/community deprecated` says: "This package has been deprecated". Source: `dist/retrievers/bm25.js`, issue `https://github.com/langchain-ai/langchainjs-community/issues/61` ("Sunsetting `@langchain/community`") |

`@langchain/community` 1.1.29 has a peer dependency on `@langchain/core ^1.1.38` plus optional peers on older packages; a plain `npm i` of all packages together failed with ERESOLVE and succeeded only with `--legacy-peer-deps` (my run, in a scratch directory). `@langchain/classic` is the v1 home of the old `langchain/...` exports.

### @langchain/pgvector (`PGVectorStore`)

Source read: `node_modules/@langchain/pgvector/dist/vectorstores.js` and `.d.ts` (version 0.1.0).

- Construct: `await PGVectorStore.initialize(embeddings, { postgresConnectionOptions | pool, tableName, columns: { idColumnName, vectorColumnName, contentColumnName, metadataColumnName }, distanceStrategy: "cosine" | "innerProduct" | "euclidean", dimensions, collectionTableName?, collectionName?, skipInitializationCheck?, schemaName?, scoreNormalization?: "distance" | "similarity" })`.
- Table it creates (`ensureTableInDatabase`): `CREATE EXTENSION IF NOT EXISTS vector;` then
  `CREATE TABLE IF NOT EXISTS <table> ("id" uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY, "content" text, "metadata" jsonb, "embedding" vector(<dimensions>))` (column names default to `id`, `text` (content), `metadata`, `embedding` (vector); constructor lines 263-266 of `vectorstores.js`; the DDL above shows `content` because the example docs name it that way, so set `columns` explicitly). If `dimensions` is not passed, the column is untyped `vector` and HNSW will not be used at query time (docstring).
- Optional collection table (only if `collectionTableName` is set): `uuid uuid PK`, `name`, `cmetadata jsonb`, and `collection_id uuid` is added to the main table.
- Inserts write only `content`, the vector, `metadata`, and optionally `collection_id` and `id`. So any extra `NOT NULL` column without a default (our `document_id`, `section`) would make inserts fail. `id` must be a valid uuid if you pass `ids` (the id column is `uuid`; deletes cast `ids::uuid[]`).
- Index: `createHnswIndex({ dimensions, m = 16, efConstruction = 64, namespace })` creates `USING hnsw ((<vector>::vector(<dimensions>)) vector_cosine_ops)`. The docstring says dimensions "up to 2000".
- Filters (`MetadataFilter`): plain equality `{ key: value }` compiles to `metadata ->> 'key' = value` (text comparison, so booleans and numbers are compared as strings). Operators: `in`, `notIn`, `arrayContains` (jsonb `?|`, any-of semantics), `gt`, `gte`, `lt`, `lte` (numeric cast), `neq`. Multiple keys are ANDed. There is no `or`, no `not`, no `like`.
- `asRetriever`: inherited from core. `vectorStore.asRetriever({ k, filter, searchType: "similarity" | "mmr", searchKwargs })` or `asRetriever(k, filter, callbacks, tags, metadata, verbose)`. Source: `@langchain/core/dist/vectorstores.d.ts` (`VectorStoreRetrieverInput`). MMR is supported through `maxMarginalRelevanceSearch`.
- Hybrid search: not present. `grep` for `tsvector`, `bm25`, `hybrid` in the package source finds nothing. The package does vector similarity only (`<=>`, `<#>`, `<->`).
- Scores: by default the retriever-level score is the raw distance (lower is better). `scoreNormalization: "similarity"` returns higher-is-better values (cosine similarity = (2 - distance) / 2). Our `sources` event uses a `score`, so set this deliberately.

Consequence: the hybrid retriever has to be our own SQL (the fallback already in `DATABASE-SCHEMA.md`) wrapped as a `BaseRetriever`, or an `EnsembleRetriever` over `PGVectorStore.asRetriever` plus a custom Postgres full-text retriever we write. `BM25Retriever` from community would need the whole corpus in memory, which defeats the "one database" design (it works for a small corpus of a few thousand chunks but is deprecated and not filter-aware).

---

## 3. PostgresSaver, state export, streaming

### Package and construction

- Package `@langchain/langgraph-checkpoint-postgres` 1.1.0. `import { PostgresSaver } from "@langchain/langgraph-checkpoint-postgres";`
- Constructors: `PostgresSaver.fromConnString(connString, { schema?: string })` or `new PostgresSaver(pool, serde?, { schema })`. Source: `dist/index.d.ts` and the package README (`https://github.com/langchain-ai/langgraphjs/blob/main/libs/checkpoint-postgres/README.md`).
- `await checkpointer.setup()` must be called the first time. Source: README ("You must call .setup() the first time you use the checkpointer").
- Tables (from `dist/migrations.js`), in the `public` schema unless `schema` is set: `checkpoint_migrations (v INTEGER PK)`, `checkpoints (thread_id TEXT, checkpoint_ns TEXT, checkpoint_id TEXT, parent_checkpoint_id TEXT, type TEXT, checkpoint JSONB, metadata JSONB, PK(thread_id, checkpoint_ns, checkpoint_id))`, `checkpoint_blobs (thread_id, checkpoint_ns, channel, version, type, blob BYTEA, PK(...))`, `checkpoint_writes (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, blob BYTEA, task_path TEXT)`.
- Messages are stored as serialized blobs in `checkpoint_blobs` (channel `messages`), not as JSON rows. So the statement in `DATABASE-SCHEMA.md` "do not read them directly" is correct.
- `thread_id` is `TEXT`; docs advise keeping it under 255 characters and using a UUID (`https://docs.langchain.com/oss/javascript/langgraph/persistence`, troubleshooting section).
- Deleting a thread: `checkpointer.deleteThread(threadId: string)` exists (`dist/index.d.ts`) and deletes from the three data tables by `thread_id` (`sql.js`). Not run.
- Not run against a live Postgres. The checkpointer pool shares the database, but should be created once and reused.

### Reading a thread for export

- `await agent.getState({ configurable: { thread_id } })` returns a `StateSnapshot` with `values`, `next`, `tasks`, `metadata`, `config`, `createdAt`, `parentConfig`. `values.messages` is the message list. Verified in a live run (with `MemorySaver`; the API is the same for any checkpointer): messages came back as `human`, `ai` (with tool call, empty content), `tool`, `ai` (final). Docs: `https://docs.langchain.com/oss/javascript/langgraph/checkpointers` ("graph.getState(config)", "graph.getStateHistory(config)").
- `agent.getStateHistory(config)` iterates all checkpoints, most recent first. Not needed for a plain export.
- Export recipe: map each message to `{ type: m.getType(), content: m.content, tool_calls: m.tool_calls, tool_call_id, name, usage }` and write JSON. Listing threads is not provided by the saver in a UI-friendly form, so keep our own `threads` table (already in the docs).

### Streaming events

- `agent.stream(input, { configurable: { thread_id }, streamMode })`. Modes (docs table): `updates` (state update after each step), `messages` (tuples of `[token, metadata]` from any LLM call), `custom` (data from tool `writer`). An array of modes yields `[mode, chunk]` pairs. Source: `https://docs.langchain.com/oss/javascript/langchain/streaming`.
- There is also a newer typed API `agent.streamEvents(input, { ...config, version: "v3" })` exposing `stream.messages` (with `message.text` async iterable), `stream.toolCalls` (`call.name`, `call.input`, `await call.output`) and `await stream.output`. It is in the same docs page. I did not run it, so I use the older modes below, which I did run.
- Live run with `streamMode: ["messages", "updates"]` against OpenRouter `openai/gpt-4o-mini` (my script, scratch dir):
  - `messages` chunks: `AIMessageChunk` with `content` text tokens, or `tool_call_chunks` (first chunk has `name` and `id`, later chunks stream the JSON `args`), metadata `langgraph_node: "model_request"`. The final chunk of each model call has `usage_metadata` (`input_tokens`, `output_tokens`) and `response_metadata.usage` containing OpenRouter's `cost`.
  - `updates` chunks: `{ model_request: { messages: [AIMessage with complete tool_calls] } }`, then `{ tools: { messages: [ToolMessage { name, tool_call_id, content, status }] } }`, then the final model update.
- Mapping to our SSE types: `token` = text content from `messages` chunks where `langgraph_node === "model_request"`; `tool_call` = complete `tool_calls` from the `model_request` update (or the first `tool_call_chunk` with `name`); `tool_result` = `ToolMessage` in the `tools` update (duration has to be measured by us between the two events); `usage` = `response_metadata.usage` of the last chunk of each model call. The `sources` and `queries` events have to be emitted by our tool through `streamMode: "custom"` (`config.writer`) or read from the structured tool result.

---

## 4. OpenRouter

All data below is from live calls on 2026-10-19 with the project key, plus the official docs and OpenAPI file (`https://openrouter.ai/openapi.yaml`).

### /api/v1/models

- Public GET, 469 models returned. Fields per model: `id`, `canonical_slug`, `hugging_face_id`, `name`, `created`, `description`, `context_length`, `architecture` (`modality`, `input_modalities`, `output_modalities`, `tokenizer`, `instruct_type`), `pricing`, `top_provider` (`context_length`, `max_completion_tokens`, `is_moderated`), `per_request_limits`, `supported_parameters`, `default_parameters`, `supported_voices`, `knowledge_cutoff`, `expiration_date`, `links`, and for some `reasoning`.
- `pricing` values are strings in USD per token (for example `"prompt": "0.00000015"`), plus optional keys such as `completion`, `input_cache_read`, `web_search`, `image`. Multiply by 1,000,000 for the per-1M price. Free variants have id suffix `:free` and price `"0"`.
- `supported_parameters` is an array. A model supports tool calling if it contains `"tools"` (and `"tool_choice"`). Example for `openai/gpt-4o-mini`: `frequency_penalty, logit_bias, logprobs, max_completion_tokens, max_tokens, prediction, presence_penalty, response_format, seed, stop, structured_outputs, temperature, tool_choice, tools, top_logprobs, top_p, web_search_options`.
- Some models carry an `expiration_date` (for example `poolside/laguna-xs-2.1` expires 2026-10-31, `qwen/qwen3.5-9b` 2026-10-21), so avoid models with one.

### Embeddings

- `POST /api/v1/embeddings` exists. Request: `model`, `input` (string or array), optional `dimensions`, `encoding_format` (`float` or `base64`). Source: OpenAPI (`/embeddings`), docs `https://openrouter.ai/docs/api-reference/embeddings/create-embeddings`.
- `GET /api/v1/embeddings/models` lists embedding models (33 today). Source: OpenAPI (`/embeddings/models`) and a live call. The list has no dimension field, and `supported_parameters` is empty; the dimension is only in some descriptions. Dimension therefore must be taken from the provider docs or measured.
- Live test: `openai/text-embedding-3-small` returned a vector of length 1536 (also through `OpenAIEmbeddings` from `@langchain/openai` with a custom `baseURL`). The response has `usage: { prompt_tokens, total_tokens, cost, ... }`. Cost for a 13-token input was 2.6e-07.
- Live test of `baai/bge-m3` failed with 404 "Model blocked by guardrail ... configurable at https://openrouter.ai/workspaces/default/guardrails". That is a setting on this account's workspace, not a model fact. Check workspace guardrails before choosing a model.

Selected embedding models (price per 1M input tokens from the live list; dimension as stated in the description or measured):

| Model | $ per 1M | Dimension | Max input tokens |
|---|---|---|---|
| `openai/text-embedding-3-small` | 0.02 | 1536 (measured) | 8192 |
| `openai/text-embedding-3-large` | 0.13 | 3072 (OpenAI model spec, not read from OpenRouter) | 8192 |
| `baai/bge-m3` | 0.01 | 1024 (description) | 8194 (blocked by this account's guardrail) |
| `qwen/qwen3-embedding-8b` | 0.01 | not stated in the OpenRouter listing, unverified | 40960 |
| `voyageai/voyage-4-lite` | 0.02 | not stated, unverified | 32000 |
| `baai/bge-base-en-v1.5` | 0.005 | 768 (description) | 512 |
| `liquid/lfm-2.5-embedding-350m:free` | 0 | 1024 (description) | 512 |

Our corpus is small (about 160 documents, roughly a few thousand chunks), so embedding cost is a fraction of a cent for any of these. `openai/text-embedding-3-small` with 1536 dimensions matches the draft DDL.

### Usage and cost in chat completions

- Usage is always returned, with no parameter. The docs state that `usage: { include: true }` and `stream_options: { include_usage: true }` are deprecated and have no effect. Source: `https://openrouter.ai/docs/guides/guides/usage-accounting`.
- Non-streaming: `usage` on the response. Streaming: the last SSE data chunk before `data: [DONE]` carries `usage`. Source: same page, confirmed live.
- Live response shape (`openai/gpt-4o-mini`, trimmed): `"usage": { "prompt_tokens": 9, "completion_tokens": 9, "total_tokens": 18, "cost": 6.75e-06, "is_byok": false, "prompt_tokens_details": { "cached_tokens": 0, "cache_write_tokens": 0, ... }, "cost_details": { "upstream_inference_cost": 6.75e-06, "upstream_inference_prompt_cost": 1.35e-06, "upstream_inference_completions_cost": 5.4e-06 }, "completion_tokens_details": { "reasoning_tokens": 0, ... } }`. In the streaming run, that same `usage` was on the final chunk, which also had `finish_reason: "stop"` (the final chunk had an empty `delta.content`).
- Unit: the docs call `cost` "the total amount charged to your account" in "credits". The fetched page does not say "USD", so the currency is documented as credits. Our `costEur` field needs a conversion factor and a note, or should be renamed. I did not verify the credit-to-USD relation on a primary page.
- Cost per call comes straight from `usage.cost`, so we do not need our own price table. Through LangChain it appears in `AIMessageChunk.response_metadata.usage.cost` (verified), and tokens in `usage_metadata`.

### Cheap models with tool calling (from the live list on 2026-10-19; prices per 1M tokens, input / output)

| Model id | Input | Output | Context | `tools` in `supported_parameters` |
|---|---|---|---|---|
| `openai/gpt-oss-20b` | $0.018 | $0.09 | 131072 | yes |
| `mistralai/mistral-nemo` | $0.029 | $0.03 | 131072 | yes |
| `deepseek/deepseek-v4.1-flash` | $0.0376 | $0.08 | 1048576 | yes |
| `openai/gpt-4o-mini` | $0.15 | $0.60 | 128000 | yes. Tool calling plus streaming plus `createAgent` verified in a live run |
| `openai/gpt-5-mini` (stronger answer model) | $0.25 | $2.00 | 400000 | yes |

Only `openai/gpt-4o-mini` was exercised end to end. The others are listed from the API fields, so test tool calling on the chosen model in story 1. Provider routing can change a model's availability and price, and the guardrail issue above shows account-specific blocks.

### @langchain/openai with a custom baseURL

Verified. `new ChatOpenAI({ model: "openai/gpt-4o-mini", apiKey, configuration: { baseURL: "https://openrouter.ai/api/v1" } })` worked with `createAgent`, tool calling, streaming and `getState`. `OpenAIEmbeddings` with the same `configuration.baseURL` worked. There is also a dedicated package `@langchain/openrouter` (0.4.17 on npm), which I did not test.

---

## 5. Tailwind CSS and DaisyUI

- Current versions on npm today: `tailwindcss` 4.3.3, `@tailwindcss/vite` 4.3.3, `daisyui` 5.7.50 (dist-tag `latest`), `@sveltejs/kit` 3.1.0, `svelte` 5.57.2. Source: `npm view`.
- DaisyUI install (official, `https://daisyui.com/docs/install/`): `npm i -D daisyui@latest`, then in `app.css`: `@import "tailwindcss";` and `@plugin "daisyui";`. No `tailwind.config.js`.
- DaisyUI for SvelteKit (`https://daisyui.com/docs/install/sveltekit/`): `npx sv create ./`, `npm install tailwindcss@latest @tailwindcss/vite@latest daisyui@latest`, add `tailwindcss()` before `sveltekit()` in `vite.config`, put the two lines above in `src/app.css`, import `../app.css` in a layout or page.
- Tailwind's own SvelteKit guide (`https://tailwindcss.com/docs/installation/framework-guides/sveltekit`) says the same, and notes that `<style>` blocks in Svelte files need `@reference "tailwindcss";` to use Tailwind theme values.
- Compatibility: `daisyui` 5.7.50 declares no peer dependencies. `@tailwindcss/vite` 4.3.3 peers on `vite ^5.2 || ^6 || ^7 || ^8`. `@sveltejs/kit` 3.1.0 peers on `vite ^8.0.12`, `svelte ^5.57.1`, `typescript ^6.0.0`, `@sveltejs/vite-plugin-svelte ^7.0.0`, and requires Node `>=22.17` (`npm view`). So the working combination is Node 22.17+, Vite 8, TypeScript 6, Tailwind 4.3, DaisyUI 5. Use a current `sv create` rather than copying older tutorials.
- Verdict for decision 18: no known blocker. The "Tailwind 4 plugin issues" risk did not show up in the official instructions. I did not run a build.

---

## 6. Licences and terms

### Wikipedia text

- Wikimedia Terms of Use, section "Licensing of Content": text is licensed under CC BY-SA 4.0 and GFDL (unversioned); reusers may comply with either or both. Source: `https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use`.
- Attribution is required "through hyperlink (where possible) or URL to the article", or a link to a stable copy that credits authors, or a list of all authors. Same source.
- Share-alike: the licence requires the same freedom for derivative works (ToU: "the same freedom to reuse and redistribute is granted to any derivative works"). The ToU page does not spell out how this applies to chunks stored in a vector store or to model answers. I did not check the CC legal code, so the legal consequence for generated answers is unverified. Practical rule: store `url` and licence string per document, show citations, and keep the app's licence statement honest. For a student project that is not redistributing the corpus, linking each source is the minimum.
- Facts alone are not covered: ToU states that facts contributed may be reused freely without attribution (this refers to sui generis database rights waived by contributors). Same source.

### MusicBrainz

- Rate limit: the IP rule is on average 1 request per second. Above that, all requests from the IP are declined with HTTP 503 until the rate drops. Global limit 300 requests per second. Source: `https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting`. (A live response also carried `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset` headers; these are not described on the page I read, so do not depend on them.)
- User-Agent: required, must let MusicBrainz contact the maintainers. Suggested format `Application name/<version> ( contact-url-or-email )`. Anonymous or blank agents are throttled harder. Same page.
- API use: "Non-commercial use of this web service is free; please see our commercial plans or contact us if you would like to use this service commercially." No API key. Source: `https://musicbrainz.org/doc/MusicBrainz_API`.
- Data licence: core data (artists, release groups, releases, recordings and so on) is CC0. Supplementary data (annotations, tags including genre associations, ratings, and some derived data) is CC BY-NC-SA 3.0. Sources: `https://musicbrainz.org/doc/About/Data_License` and `https://musicbrainz.org/doc/MusicBrainz_Database`. Consequence: titles and dates are free to use; do not store MusicBrainz tags or ratings in the corpus without the NC-SA conditions.

### Encyclopaedia Metallum

- Reachable pages: `https://www.metal-archives.com/content/rules`, `/content/faq`, `/content/pp` ("Terms of Service and Privacy Policy", last updated 17 May 2023), `/content/tools`, `/robots.txt`. `/content/tos` returns 404.
- `robots.txt` says: `User-agent: *` disallows `/affiliate/`, `/history/`, `/report/`, `/forum/`, `/users/` and sets `Crawl-delay: 3`; it blocks `dotbot` and `SemrushBot` entirely. Source: `https://www.metal-archives.com/robots.txt`.
- I searched the rules, FAQ and ToS/privacy pages for scraping, crawling, API, reuse and licence wording and found no clause about scraping or reuse and no content licence statement. The ToS page is about accounts and privacy. The rules page requires contributors to write in their own words and forbids plagiarism. That is my keyword search of the pages as served, not a legal review. Conclusion: there is no explicit permission to copy the content and no explicit ban found. The copyright notice is "© 2002-2026 Encyclopaedia Metallum". Keep the decision not to scrape, but the reason becomes "no licence or permission found, crawl-delay 3, content is user-written under the site's copyright" instead of "terms unchecked".

---

## 7. MusicBrainz web service v2

Official reference: `https://musicbrainz.org/doc/MusicBrainz_API` and `https://musicbrainz.org/doc/MusicBrainz_API/Search`. JSON: add `fmt=json` or send `Accept: application/json`. Requests below were made once each, 1.5 seconds apart, with the User-Agent `MetalArchiveAssistantResearch/0.1 ( cristi-mihail.filip@greenbay-software.de )`.

### Resolve an artist name to an MBID (search)

`GET https://musicbrainz.org/ws/2/artist?query=artist:Metallica&fmt=json&limit=3`

Response (trimmed): `{ "created": "...", "count": 13, "offset": 0, "artists": [ { "id": "65f4f0c5-ef9e-490c-aee3-909e7ae6b2ab", "name": "Metallica", "score": 100, "type": "Group", "country": "US", "disambiguation": null }, { "id": "3cc58f89-...", "name": "Metallica 2", "score": 55, "disambiguation": "Chilean tribal ambient/metal" }, { "name": "Metallica Reloaded", "score": 54, "disambiguation": "Metallica tribute band" } ] }`.

Pick the top hit only when `score` is high and the name matches exactly. Otherwise return the candidates (with `disambiguation` and `country`) to the model so it can ask the user. Names like "Mgła" need the exact spelling. Search `limit` accepts 1 to 100 (default 25). Source: Search page.

### Browse release groups of an artist (the main request)

`GET https://musicbrainz.org/ws/2/release-group?artist=65f4f0c5-ef9e-490c-aee3-909e7ae6b2ab&type=album&fmt=json&limit=100&offset=0`

- Response top level: `{ "release-group-count": 979, "release-group-offset": 0, "release-groups": [ ... ] }`.
- One item (live, trimmed, a live album):

```json
{
  "id": "03810812-26d5-3d4e-b1df-04012eb0d949",
  "title": "2004-10-17: Washington, DC, USA",
  "primary-type": "Album",
  "primary-type-id": "f529b476-6e62-324f-b0aa-1f3e33d313fc",
  "secondary-types": ["Live"],
  "secondary-type-ids": ["6fd474e2-6b58-3102-9d17-d6f7eb7da0a0"],
  "first-release-date": "2004-10",
  "disambiguation": ""
}
```

- A studio album has `"secondary-types": []`, for example `{ "title": "Master of Puppets", "primary-type": "Album", "secondary-types": [], "first-release-date": "1986-03-03" }`.
- `first-release-date` can be `YYYY-MM-DD`, `YYYY-MM` or `YYYY` (seen in the same response), or empty. Parse partial dates.
- `type=album` selects primary type Album, and it still returns live, compilation and soundtrack albums as primary type Album with `secondary-types` filled. For Metallica that is 979 release groups, almost all live recordings. The type parameter takes a pipe list, for example `type=album|ep` (official example: Autechre albums and EPs).
- Studio albums = `primary-type == "Album"` (or `"EP"`) and `secondary-types` empty. Verified on Metallica: after filtering the 100-item first page the studio albums are Kill 'Em All (1983-07-25), Ride the Lightning (1984-07-27), Master of Puppets (1986-03-03), ...And Justice for All (1988-08-25), Metallica (1991-08-12), Load (1996-05-04), Reload (1997-11-15), St. Anger (2003-06-04), Death Magnetic (2008-09-06), Lulu (2011-10-31, with Lou Reed), Hardwired... to Self-Destruct (2016-11-08), 72 Seasons (2023-04-14). The first page contained all 12 of them, but that is luck: results are not sorted by date, and order is only "consistent". Doc: "If you need to sort the entities, you will have to fetch all entities (see Paging) and sort them yourself."
- Paging: browse requests are the only ones with `offset`, `limit` default 25, maximum 100. Metallica needs 10 pages (979 / 100) for `type=album`, which is 10 seconds at 1 request per second. Source: doc section "Paging".
- Cheaper alternative with server-side filtering (search): `GET /ws/2/release-group?query=arid:<MBID> AND primarytype:album AND NOT secondarytype:*&fmt=json&limit=100` (URL-encode the query). Live result: `count: 16`, containing the 12 studio albums plus noise ("Destroyed in the Mosh" (2016), "Live in Concert" (2017-11-17) and one entry without `first-release-date`). Search items have a `score` and `artist-credit` instead of the browse shape, and fields can be absent (`first-release-date` was missing on one item, so guard for it). A name-only search `query=artist:Metallica AND ...` is wrong: it matched a bogus "Nobelium" entry credited to a different artist (credit name "Metallica", artist "Zippy Kid"), so always use `arid:` with the MBID.
- Also available: `release-group-status=website-default` on browse, which gives the same list as the website's default overview (excludes groups with only promotional, bootleg or pseudo-releases). Source: doc section "Release (Group) Type and Status". I did not test it.
- Release lookup: `GET /ws/2/release?release-group=<RG-MBID>&status=official&fmt=json&limit=2` returns `{ "release-count": 70, "release-offset": 0, "releases": [ { "id", "title", "status": "Official", "country", "release-events": [ { "date": "1986-03-03", "area": {...} } ], "barcode", ... } ] }`. Releases are limited so that a page has no more than 500 tracks, so advance `offset` by the number of items returned, not by `limit`. For the discography tool, release groups are enough and avoid this.
- Recommendation: browse by `artist=<MBID>&type=album|ep&limit=100` and loop until `offset >= release-group-count`, filter `secondary-types.length === 0` on the client, sort by `first-release-date`, and cache per MBID. For big artists, prefer the search with `arid:` and the secondary-type exclusion (one request), and fall back to browse when the count is above 100.

---

## Documents that need changing

`DOMAIN.md`
- Line 13 (data sources table, `music-wiki` row): "MIT licensed". Change to: dataset card says MIT, but the text is Wikipedia text under CC BY-SA 4.0 and GFDL, so keep `url` and attribution per document. Also add: "twelve splits" stays correct, but band pages for some top bands are missing, and a few pages sit in the wrong split.
- Line 14: "Wikipedia text is commonly CC BY-SA, so keep url and attribution. Verify before redistributing." Now verified: Wikimedia ToU requires CC BY-SA 4.0 (or GFDL) and attribution by link or author list. Replace "commonly" with the cited terms.
- Line 15: "No key, descriptive User-Agent required, max 1 request per second. Verify terms on the official page." Verified. Add that non-commercial use is free, commercial use needs a plan, and that MusicBrainz tags and ratings are CC BY-NC-SA while core data is CC0.
- Line 17: "Encyclopaedia Metallum scraping (terms not checked, no free dump found)". Change to: no scraping clause and no content licence found on the site pages, robots.txt has Crawl-delay 3, content is under the site's copyright, so no permission to reuse.
- Line 19: "Unverified: how many seed bands the music-wiki snapshot actually covers." Replace with the measured result (8 of 14 probe bands, 5 of 6 genre pages; Black Sabbath, Judas Priest, Metallica, Megadeth, Opeth and Deep Purple are missing as band pages).
- Line 72 (`musicbrainz_discography` row): default "studio album and EP" needs the rule: primary type Album or EP with an empty `secondary-types`, and a paging note (Metallica has 979 album release groups).

`DECISIONS.md`
- Row 5 and row 6: "Static, MIT licensed, reproducible." Replace "MIT licensed" with "dataset card MIT, text CC BY-SA". Row 6 also needs the fallback made the main path for missing bands: Wikipedia API gap filling will be needed for several famous bands (Black Sabbath, Judas Priest, Metallica, Megadeth, Opeth, Deep Purple).
- Row 7: "Terms unchecked, no free dump found." Update as in `DOMAIN.md` line 17.
- Row 14: "API mismatch in JS. Fall back to MemorySaver plus own messages table." The JS API exists (`PostgresSaver.fromConnString`, `setup()`, `agent.getState`). Remove or soften the risk.
- Row 18: "Tailwind 4 plugin issues." Official instructions work with `@plugin "daisyui"`; add the version floor (Node 22.17+, Vite 8, TypeScript 6 with SvelteKit 3.1).
- Row 20: "Embedding endpoint or model unavailable." The endpoint exists and `openai/text-embedding-3-small` works with 1536 dimensions. Note that workspace guardrails can block models (bge-m3 was blocked on this account).
- "Open facts" section (lines 37 to 44): mark each item as answered and point to this file.

`ARCHITECTURE.md`
- Retrieval section: "Hybrid (story 15): BM25 retriever plus the vector retriever combined with `EnsembleRetriever`". `BM25Retriever` is in the deprecated `@langchain/community`, runs in memory over all documents and does not query Postgres. `EnsembleRetriever` is in `@langchain/classic` (`@langchain/classic/retrievers/ensemble`). Make the hand-written SQL (vector plus `ts_rank`, fused with RRF) the main hybrid path, wrapped in a custom `BaseRetriever`.
- "To verify when implementing: hybrid configuration in `@langchain/pgvector`". There is none. Replace with the fact.
- Streaming events table: add the source of each event (`messages` mode for tokens, `updates` mode for `tool_call` and `tool_result`, `custom` mode or tool result for `sources` and `queries`). The `usage` row: payload `costEur` is wrong in unit. OpenRouter reports `usage.cost` in credits, and the app must convert, or the field should be named `cost`.
- Cost guard paragraph ("Cost per call comes from OpenRouter's usage fields where available, otherwise from per-model prices in config"): now verified. `usage.cost` is always present, so the per-model price table in config is not needed. Say the unit is OpenRouter credits and state the EUR conversion used for the 1 EUR and 4 EUR caps.

`DATABASE-SCHEMA.md`
- Line 3: "pgvector/pgvector:pg16 (as suggested by the LangChain JS docs)". I did not verify the LangChain docs claim. Docker Hub has tags pg13 to pg18 for `pgvector/pgvector` (`https://hub.docker.com/v2/repositories/pgvector/pgvector/tags`), so pg16 is valid but not the newest.
- Line 5 and the `chunks` DDL: `PGVectorStore` expects `id uuid`, `content text`, `metadata jsonb`, vector column, and inserts only those. Our `chunks.id BIGSERIAL`, `document_id BIGINT NOT NULL` and `section` would break inserts through `PGVectorStore` (it never writes `document_id`). Options: use a uuid `id`, make `document_id` nullable or put `document_id` into `metadata`, set `skipInitializationCheck: true`, and map `columns`; or write our own retriever and insert code and skip `PGVectorStore` for writes. `tsv GENERATED` is fine because the store never writes it.
- Line 43: "for example 1024, 1536 or 3072". `PGVectorStore.createHnswIndex` documents a limit of 2000 dimensions for HNSW on `vector`, so 3072 (`text-embedding-3-large`) needs `dimensions: 1536` on the request (the OpenRouter embeddings endpoint has a `dimensions` parameter) or a different index type. Say so.
- Line 112: statement is correct (messages are in `checkpoint_blobs`). Replace "Verify the exact API" with `agent.getState({ configurable: { thread_id } })` and `values.messages`.

`IMPLEMENTATION-PLAN.md`
- Story 1 "Verify first" (line 37): replace with the confirmed versions and Node requirement; record the chosen chat model, rewrite model and embedding model.
- Story 2 "Verify first" (line 49): coverage result and licences are now known; the seed script must search all splits by `url`, handle the missing top bands via the Wikipedia API, and strip category pages (rows under about 300 characters) and "References" or "External links" sections.
- Story 3 "Verify first" (line 61): table layout answered (see `DATABASE-SCHEMA.md` above).
- Story 5 (line 82) and story 14 (line 174): `PostgresSaver` and `getState` answered.
- Story 15 (line 183): `@langchain/pgvector` has no hybrid; `BM25Retriever` is in-memory and in a deprecated package; use the SQL RRF fallback.
- Chunking in story 3: headings in `wikipedia_music` text are bare lines with no markers, so "section-aware splitter" needs a heading heuristic (short line, no final period) or splitting by blank lines.
- Story with `musicbrainz_discography` (line 111): the client must page (`limit=100`) and filter `secondary-types`; two to ten calls per artist at 1 request per second. Cache by MBID.

`SECURITY.md`
- Line 35: "MusicBrainz client enforces 1 request per second with a queue, a timeout, and a descriptive User-Agent." Correct. Add handling for HTTP 503 as the rate-limit signal.
