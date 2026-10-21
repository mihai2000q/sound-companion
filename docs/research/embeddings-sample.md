# Real embeddings on a Corpus sample

Date: 2026-10-21. Issue 16 (Story 3, "Verify first"). Script: `sound-companion.server/scripts/embed_sample.py`, run against the stored Corpus (276 documents) with the project key, model `openai/text-embedding-3-small`, `POST {OPENROUTER_BASE_URL}/embeddings` called with `httpx`. Total spend about 0.0003 credits across all probes.

The script splits with a rough stand-in (title and alias line, then 800 characters with 100 overlap, per section). The real splitter is issue 17, so chunk counts here are an estimate, not the final number.

| Question | Result |
|---|---|
| Dimension | 1536, from 50 real chunks (50 vectors back for 50 inputs). |
| Corpus size | 6,431 rough chunks, 4,356,820 characters. |
| Tokens per chunk | 158.8 on average (4.28 characters per token, header line included). |
| Does the call return its cost? | Yes. The response body has `usage: {prompt_tokens, total_tokens, cost, is_byok, cost_details}`. Read `body["usage"]["cost"]`. The 50-chunk call reported 7,939 tokens and cost 0.00015878. |
| Cost per chunk | 3.18e-06 credits. |
| Cost for the whole Corpus | About 0.02 credits (6,431 chunks), matching 1.02M tokens at the listed 0.02 per 1M. |
| Largest batch accepted | 2,048 inputs. 4,096 returned HTTP 400 `Invalid 'input': array length must be 2048 or less.` 512 real chunks (about 80k tokens) in one call returned 200. A total-token limit per request was not reached, so it is unknown. |
| Rate limit | No 429 and no `ratelimit` or `retry` response headers across 12 calls in a few seconds. Not measured beyond that. |

## Findings

- **Cost is in the response body, but `OpenAIEmbeddings` hides it.** `embed_documents` returns `list[list[float]]` and the library source never touches `usage` or `cost`. To log embedding cost in `usage_log` (the budget guard needs it), the ingest has to call the endpoint itself (`httpx`, as the script does) or the `openai` client's raw response, not `OpenAIEmbeddings`.
- **Batch size is a choice, not a constraint.** The hard limit is 2,048 inputs. A batch of 100 to 256 keeps requests small, and the whole Corpus is then 25 to 65 calls.
- **Not tested:** token-limit behaviour above 512 chunks per call, sustained rate limits, `OpenAIEmbeddings` with `check_embedding_ctx_length=False` against OpenRouter (Story 1 passed with one short string).
