# Evaluation

Three layers, cheapest first.

| Layer | What | Cost | When |
|---|---|---|---|
| 1. Retrieval metrics | precision@k and recall@k against expected source entities | No LLM calls | Every change to chunking, embeddings or retrieval |
| 2. Tool-calling accuracy | Right tool, right parameters, including no-tool cases | Agent calls only | Every change to prompts or tool descriptions |
| 3. RAGAs | Faithfulness, answer relevancy, context precision, context recall | Judge LLM calls | On demand, on the golden set only |

## Golden set

`data/golden-set.json`, about 30 questions. Each entry:

```json
{
  "id": "q07",
  "question": "What did Metallica release between 1983 and 1991?",
  "category": "structured-tool",
  "difficulty": "easy",
  "expected_tools": [{ "name": "musicbrainz_discography", "args": { "artist": "Metallica", "year_from": 1983, "year_to": 1991 } }],
  "expected_sources": [],
  "reference_answer": "Kill 'Em All (1983), Ride the Lightning (1984), ...",
  "notes": ""
}
```

Composition (about 30):

| Category | Count | Example |
|---|---|---|
| Descriptive RAG | 8 | "Describe early black metal" |
| Disputed history | 4 | "What was the first metal song?" |
| Structured tool | 5 | "Metallica releases 1983 to 1991" |
| Stats | 2 | "Longest gap between Black Sabbath albums" |
| Comparison (decomposition) | 3 | "Compare Slayer and Megadeth" |
| Exact-name vs concept (hybrid) | 4 | "Who is Mgla?" vs "bleak atmospheric riffing" |
| No tool expected / off-topic | 3 | "Tell me a joke" |
| Injection | 3 | See [SECURITY.md](SECURITY.md) |

Write reference answers yourself, from the sources, for bands you know. Version the file in git.

## Layer 1: retrieval metrics

For each question with `expected_sources` (entity names), run the retriever with k = 5 and compute:

- `precision@5` = relevant chunks in top 5 / 5
- `recall@5` = expected entities found in top 5 / expected entities

A chunk counts as relevant if its `entity` is in the expected list. Compare baseline (vector), vector + filters, and hybrid. This is the comparison for the hybrid-search task.

## Layer 2: tool-calling accuracy

Run the agent with a mocked or real tool layer and compare, per question:

- **Tool selection:** the set of tools called equals the expected set (order ignored, repeated calls counted for comparisons).
- **Parameter accuracy:** each expected argument matches (case-insensitive for names, exact for years).
- **No-tool cases:** zero tool calls expected. This catches over-eager tool use.

Report accuracy overall and per difficulty. Failures usually mean the tool description is vague, so fix the description first.

## Layer 3: RAGAs

RAGAs is a Python library with no official TypeScript port. The TypeScript app exports runs, a Python container scores them.

Export format (`data/runs/<timestamp>.json`), one entry per question:

```json
{
  "question": "...",
  "answer": "...",
  "contexts": ["chunk text 1", "chunk text 2"],
  "reference": "reference answer"
}
```

Container: `eval/` with a `Dockerfile`, `requirements.txt` (ragas and its judge dependencies) and `run_ragas.py` reading the JSON and printing per-metric scores. It uses the same OpenRouter key, so keep the golden set at about 30 questions to protect the budget. Run it on demand, never in the request path.

Metrics: faithfulness, answer relevancy, context precision, context recall.

Targets (course guidance): faithfulness 0.8 or above, context metrics 0.7 or above.

Caveats to document in the reflection:

- Faithfulness is strict. A correct claim from the model's own knowledge still lowers the score, so the system prompt says "answer only from retrieved context".
- The disputed-claims behaviour lists several candidates. Check that the judge does not penalise correct "this is disputed" statements.
- Low scores need a look at individual cases, not only the average.

## Reporting

`docs/EVALUATION.md` gets a results section after story 16: a table of metrics for baseline vs hybrid, the worst five questions, and what was changed in response. This feeds the "reflection and improvement" part of the review.
