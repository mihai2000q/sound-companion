# Evaluation

Three layers, cheapest first.

| Layer | What | Cost | When |
|---|---|---|---|
| 1. Retrieval metrics | precision@k and recall@k against expected source pages | No LLM calls | Every change to chunking, embeddings or retrieval |
| 2. Tool-calling accuracy | Right tool, right parameters, including no-tool cases | Agent calls only | Every change to prompts or tool descriptions |
| 3. RAGAs | Faithfulness, answer relevancy, context precision, context recall | Judge LLM calls | On demand, on the golden set only |

## Golden set

`data/golden-set.json`, about 31 questions when complete. Version 0 (Story 4) has 14 retrieval questions with expected sources and reference answers (descriptive, comparison, alias, exact-term, convention-conflict, textbook) and 3 that need a clarifying question. Story 15 (issue #88) adds 8 exact-term and Alias questions for the hybrid comparison (q18 to q25: Rhodes piano, kalimba, bari sax, 12-bar blues, Stuttgart pitch, Helmholtz pitch notation, viola da gamba, Eb clarinet), each an Alias of one Corpus page, so there are now 22 retrieval questions. Before them, 3 of the 14 were exact-term or Alias queries (q04, q05, q13), plus q06, which asks for German note names. No German-note-name question was added, because q06 covers it and no Corpus page was checked for it. The saved `vector-baseline` was made on the 14 questions, so the comparison uses `vector-baseline-25q` (same retriever, the 22-question set, golden-set hash in the file). The tool, no-tool and injection questions come with Story 5. Each entry:

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

Run it with `uv run python -m scripts.eval_retrieval` (`-k` changes k, `--golden-set` picks another file, `--mode vector|hybrid` picks the retriever and defaults to the `RETRIEVER_MODE` setting). It first checks that every expected source, and every clarification option, is a Corpus title or Alias, and stops naming the ones that are not. Details of the numbers:

- An expected Alias is mapped to its page, so a title and its Alias expected together count as one page.
- `precision@k` always divides by k, so a query that returns fewer than k chunks scores lower.
- The overall figures are the mean over the questions, not over chunks.
- Entries whose `expected_behaviour` is not `answer` have nothing to find and are skipped (listed at the end of the run).
- The run costs only the query embeddings (about 0.000004 credits for 14 questions).

### Saving a run and comparing it with the baseline

Every change to chunking, embeddings or retrieval gets a saved run, so it can be compared with the baseline:

```text
uv run python -m scripts.eval_retrieval --label hybrid-rrf
uv run python -m scripts.compare_runs eval/results/2026-10-22-vector-baseline.json eval/results/<date>-hybrid-rrf.json
```

- `--label` writes `eval/results/<date>-<label>.json`: the label, the date, the settings (retriever, k, filters, embedding model, chunking, index options, Corpus and golden-set sizes, golden-set hash, git commit) and the per-question and overall metrics with the retrieved sections. A saved file is never overwritten, pick a new label. The files are committed.
- `scripts.compare_runs` prints the change per question and overall (second run minus first) and the settings that differ, so a change in the numbers can be tied to the change that caused it. Compare runs made on the same golden set (the hash is saved).
- `--filters` restricts each question by its expected pages' topics: `topics-oracle` (an upper bound for topic filters) or `topics-mismatch` (a control that must score 0).
- A new retriever (Story 15) implements the `Retriever` interface and is passed to `evaluate` (see `scripts/eval_retrieval.py`), the saved settings then name it.
- The baseline and what it showed are in [research/retrieval-baseline.md](research/retrieval-baseline.md). Compare vector-only, vector with filters, and hybrid. This is the comparison for the hybrid-search task, done in issue 89: [research/hybrid-vs-vector.md](research/hybrid-vs-vector.md) (vector and hybrid, each with and without rewrite, on the 22-question set), with the default kept at `vector` (decision 71). `scripts.compare_runs` also prints the exact-term and alias group (golden-set categories `exact-term` and `alias`).

## Layer 2: tool-calling accuracy

Run the agent and compare, per question:

- **Tool selection:** the set of tools called equals the expected set (order ignored, repeated calls counted for comparisons).
- **Parameter accuracy:** each expected argument matches (case-insensitive for names, exact for notes and numbers, with notes compared after normalising enharmonic spelling only when the question allows it).
- **No-tool cases:** zero tool calls expected. This catches over-eager tool use.

Report accuracy overall and per difficulty. Failures usually mean the tool description is vague, so fix the description first. Deterministic checks are fast and free, so run them on every prompt change. Optionally add a judge on ambiguous cases, as in the course.

Run it with `uv run python -m scripts.eval_tools [--label L] [--model ID] [--real-retriever]` on `data/golden-tools.json` (20 cases: tool-rule, tool-instrument, Candidates, comparison, search and no-tool). Details of the numbers:

- Tool selection compares tool names as a multiset, so the comparison cases expect two `search_knowledge_base` calls, and a no-tool case fails on any call.
- Parameter accuracy is the share of cases with arguments to check where every listed argument matches. Only the listed arguments are checked, free-text ones like `query` are left out. Names (`instrument`, `scale`, `direction`, `source_type`) ignore case, notes and numbers are exact, and `{"any_of": [...]}` lists accepted spellings.
- Searches are answered by a stub by default (no database, see decision 59). A run costs about 72k tokens on `gpt-4o-mini`.
- With `--label` the run is saved as `eval/results/<date>-tools-<label>.json`, with hashes of the system prompt and of every tool description, so `scripts.compare_runs A B` shows which one changed next to the cases that flipped.

Also unit-test the tools directly with pytest (no LLM): the expected outputs from the research, for example `find_chords_from_notes(["D","F","A","C"])` in `pychord` gives `Dm7` and `F6/D`, written C4 on a B-flat clarinet sounds `Bb3`, and 450 Hz is A4 plus about 39 cents.

## Injection tests

`data/injection-tests.json` (14 cases, the table in [SECURITY.md](SECURITY.md#injection-test-set)), run with `uv run python -m scripts.eval_injection [--repeats N] [--model ID] [--only ids] [--label L]`. It prints pass or fail per case and exits 1 on a failure.

- **Request and tool cases** (oversized input, control characters, a bad `thread_id`, a 5,000-note chord, `H99`, `Xyz`) need no model and run once. A request case uses a stand-in agent that records being reached, so it proves the refusal came before any model call. They also run in `pytest` (`tests/test_injection_eval.py`).
- **Agent cases** (direct override, prompt leak, off-domain, planted chunk, mocked tool result, delimiter escape) run on the chat model, `--repeats` times (default 3), and pass only when every run passes. Searches return planted chunks from an in-memory retriever, never the Corpus. The checks are plain: no `PWNED` or prompt text in anything the model said, a tool-call limit (none for `chord_info`), and for the planted cases an answer that still mentions the subject. `pytest` tests the checks with scripted models that obey or resist.
- With `--label` the run is saved as `eval/results/<date>-injection-<label>.json` and `scripts.compare_runs A B` shows the cases that flipped. First run on `gpt-4o-mini` (3 runs per agent case, 2026-10-27): 14 of 14 pass, saved as `injection-baseline`.

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
