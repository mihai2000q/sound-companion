# Evaluation

Three layers, cheapest first.

| Layer | What | Cost | When |
|---|---|---|---|
| 1. Retrieval metrics | precision@k and recall@k against expected source pages | No LLM calls | Every change to chunking, embeddings or retrieval |
| 2. Tool-calling accuracy | Right tool, right parameters, including no-tool cases | Agent calls only | Every change to prompts or tool descriptions |
| 3. RAGAs | Faithfulness, answer relevancy, context precision, context recall | Judge LLM calls | On demand, on the golden set only |

## Golden set

`data/golden-set.json`, about 31 questions when complete. Version 0 (Story 4) has 14 retrieval questions with expected sources and reference answers (descriptive, comparison, alias, exact-term, convention-conflict, textbook) and 3 that need a clarifying question. The tool, no-tool and injection questions come with Story 5. Each entry:

```json
{
  "id": "q05",
  "question": "Which chord is made of the notes D, F, A and C?",
  "category": "tool-candidates",
  "difficulty": "medium",
  "expected_tools": [{ "name": "chord_info", "args": { "notes": ["D","F","A","C"] } }],
  "expected_sources": ["Seventh chord", "Chord notation"],
  "reference_answer": "Dm7, or F6/D (two Candidates, they differ by which note is heard as the root).",
  "notes": ""
}
```

An entry may have `expected_behaviour`: `answer` (the default), `clarify` (the bot asks one clarifying question and lists `clarification_options`, page titles that exist in the Corpus, and does not answer yet) or `decline`. A `clarify` entry has no `expected_sources`, and its `reference_answer` is the clarifying question. The retrieval metrics skip every entry that is not `answer`. The agent checks (layer 2) read `expected_behaviour`: a clarifying question must name the options, and a clear question must not get one.

Composition:

| Category | Count | Example |
|---|---|---|
| Descriptive, theory | 5 | "What is the circle of fifths?" |
| Descriptive, instruments | 5 | "How does a clarinet produce sound, and what is the register break?" |
| Tool, rule-based | 5 | "Which notes are in the C major scale?" / "What interval is C4 to G4?" |
| Tool, instrument | 4 | "What does a B-flat clarinet sound for a written C?" / "How many cents sharp is 450 Hz?" |
| Tool with Candidates | 2 | "Which chord is D, F, A, C?" |
| Comparison (decomposition) | 3 | "How do the viola and violin differ?" / "Compare the Dorian and Mixolydian modes" |
| Convention conflict | 4 | "What is middle C called, and what do Germans call B-flat?" |
| Alias | 1 | "Is a cor anglais the same as an English horn?" |
| Needs clarification | 3 | "Tell me about the guitar." |
| No tool expected / off-topic | 2 | "Tell me a joke" |
| Injection | 3 | See [SECURITY.md](SECURITY.md) |

The research agents drafted sixteen questions with expected pages (see [research/music-theory-data.md](research/music-theory-data.md) and [research/instruments-data.md](research/instruments-data.md)). Use them as the starting set and write reference answers yourself, from the sources. Version the file in git.

## Layer 1: retrieval metrics

For each question with `expected_sources` (page titles), run the retriever with k = 5 and compute:

- `precision@5` = relevant chunks in top 5 / 5
- `recall@5` = expected pages found in top 5 / expected pages

A chunk counts as relevant if its `title` or one of its Aliases is in the expected list.

Run it with `uv run python -m scripts.eval_retrieval` (`-k` changes k, `--golden-set` picks another file). It first checks that every expected source, and every clarification option, is a Corpus title or Alias, and stops naming the ones that are not. Details of the numbers:

- An expected Alias is mapped to its page, so a title and its Alias expected together count as one page.
- `precision@k` always divides by k, so a query that returns fewer than k chunks scores lower.
- The overall figures are the mean over the questions, not over chunks.
- Entries whose `expected_behaviour` is not `answer` have nothing to find and are skipped (listed at the end of the run).
- The run costs only the query embeddings (about 0.000004 credits for 14 questions). Compare vector-only, vector with filters, and hybrid. This is the comparison for the hybrid-search task. Include exact-term queries ("Neapolitan sixth") and concept queries.

## Layer 2: tool-calling accuracy

Run the agent and compare, per question:

- **Tool selection:** the set of tools called equals the expected set (order ignored, repeated calls counted for comparisons).
- **Parameter accuracy:** each expected argument matches (case-insensitive for names, exact for notes and numbers, with notes compared after normalising enharmonic spelling only when the question allows it).
- **No-tool cases:** zero tool calls expected. This catches over-eager tool use.

Report accuracy overall and per difficulty. Failures usually mean the tool description is vague, so fix the description first. Deterministic checks are fast and free, so run them on every prompt change. Optionally add a judge on ambiguous cases, as in the course.

Also unit-test the tools directly with pytest (no LLM): the expected outputs from the research, for example `find_chords_from_notes(["D","F","A","C"])` in `pychord` gives `Dm7` and `F6/D`, written C4 on a B-flat clarinet sounds `Bb3`, and 450 Hz is A4 plus about 39 cents.

## Layer 3: RAGAs

RAGAs is a Python library, and the backend is Python, so it runs in the same project.

Export format (`data/runs/<timestamp>.json`), one entry per question:

```json
{
  "question": "...",
  "answer": "...",
  "contexts": ["chunk text 1", "chunk text 2"],
  "reference": "reference answer"
}
```

Runner: `sound-companion.server/eval/run_ragas.py` reads the JSON and prints per-metric scores (RAGAs dependencies in an optional extras group so they do not bloat the app image). It uses the same OpenRouter key, so keep the golden set at about 31 questions to protect the budget. Run it on demand, never in the request path. Tool-only questions have no retrieved contexts, so score them with layers 1 and 2 and exclude them from the context metrics.

Metrics: faithfulness, answer relevancy, context precision, context recall.

Targets (course guidance): faithfulness 0.8 or above, context metrics 0.7 or above.

Caveats to document in the reflection:

- Faithfulness is strict. A correct claim from the model's own knowledge still lowers the score, so the system prompt says "answer only from retrieved context and tool results".
- Tool results are not retrieved context. Answers that rely on a tool result may score lower on faithfulness unless the tool output is included in the contexts passed to RAGAs. Decide this in story 16.
- Convention-conflict answers list several Conventions. Check that the judge does not penalise correct "sources differ" statements.
- Low scores need a look at individual cases, not only the average.

## Reporting

`docs/EVALUATION.md` gets a results section after story 16: a table of metrics for vector-only vs hybrid, the worst five questions, and what was changed in response. This feeds the "reflection and improvement" part of the review.
