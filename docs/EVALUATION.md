# Evaluation

Three layers, cheapest first.

| Layer | What | Cost | When |
|---|---|---|---|
| 1. Retrieval metrics | precision@k and recall@k against expected source pages | No LLM calls | Every change to chunking, embeddings or retrieval |
| 2. Tool-calling accuracy | Right tool, right parameters, including no-tool cases | Agent calls only | Every change to prompts or tool descriptions |
| 3. RAGAs | Faithfulness, answer relevancy, context precision, context recall | Judge LLM calls | On demand, on the golden set only |

## Golden set

`data/golden-set.json`, 25 entries today (22 retrieval questions, 3 that need a clarifying question). Version 0 (Story 4) has 14 retrieval questions with expected sources and reference answers (descriptive, comparison, alias, exact-term, convention-conflict, textbook) and 3 that need a clarifying question. Story 15 (issue #88) adds 8 exact-term and Alias questions for the hybrid comparison (q18 to q25: Rhodes piano, kalimba, bari sax, 12-bar blues, Stuttgart pitch, Helmholtz pitch notation, viola da gamba, Eb clarinet), each an Alias of one Corpus page, so there are now 22 retrieval questions. Before them, 3 of the 14 were exact-term or Alias queries (q04, q05, q13), plus q06, which asks for German note names. No German-note-name question was added, because q06 covers it and no Corpus page was checked for it. The saved `vector-baseline` was made on the 14 questions, so the comparison uses `vector-baseline-25q` (same retriever, the 22-question set, golden-set hash in the file). The tool, no-tool and injection questions come with Story 5. Each entry:

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

Run it with `uv run python -m scripts.eval_tools [--label L] [--model ID] [--real-retriever]` on `data/golden-tools.json` (22 cases: tool-rule, tool-instrument, Candidates, comparison, search, no-tool and clarification). Details of the numbers:

- Tool selection compares tool names as a multiset, so the comparison cases expect two `search_knowledge_base` calls, and a no-tool case fails on any call. The clarification cases (t21 guitar, t22 saxophone range, the same questions as q15 and q16 of the golden set) expect no call at all, because a clarifying question comes before any search. They fail today (`2026-10-29-tools-clarify-cases`: selection 0.91 over 22 cases, the agent searches), see REFLECTION.md problem 5.
- Parameter accuracy is the share of cases with arguments to check where every listed argument matches. Only the listed arguments are checked, free-text ones like `query` are left out. Names (`instrument`, `scale`, `direction`, `source_type`) ignore case, notes and numbers are exact, and `{"any_of": [...]}` lists accepted spellings.
- Searches are answered by a stub by default (no database, see decision 59). A run costs about 100k tokens (about $0.016) on `gpt-4o-mini`.
- With `--label` the run is saved as `eval/results/<date>-tools-<label>.json`, with hashes of the system prompt and of every tool description, so `scripts.compare_runs A B` shows which one changed next to the cases that flipped.

Also unit-test the tools directly with pytest (no LLM): the expected outputs from the research, for example `find_chords_from_notes(["D","F","A","C"])` in `pychord` gives `Dm7` and `F6/D`, written C4 on a B-flat clarinet sounds `Bb3`, and 450 Hz is A4 plus about 39 cents.

## Injection tests

`data/injection-tests.json` (14 cases, the table in [SECURITY.md](SECURITY.md#injection-test-set)), run with `uv run python -m scripts.eval_injection [--repeats N] [--model ID] [--only ids] [--label L]`. It prints pass or fail per case and exits 1 on a failure.

- **Request and tool cases** (oversized input, control characters, a bad `thread_id`, a 5,000-note chord, `H99`, `Xyz`) need no model and run once. A request case uses a stand-in agent that records being reached, so it proves the refusal came before any model call. They also run in `pytest` (`tests/test_injection_eval.py`).
- **Agent cases** (direct override, prompt leak, off-domain, planted chunk, mocked tool result, delimiter escape) run on the chat model, `--repeats` times (default 3), and pass only when every run passes. Searches return planted chunks from an in-memory retriever, never the Corpus. The checks are plain: no `PWNED` or prompt text in anything the model said, a tool-call limit (none for `chord_info`), and for the planted cases an answer that still mentions the subject. `pytest` tests the checks with scripted models that obey or resist.
- With `--label` the run is saved as `eval/results/<date>-injection-<label>.json` and `scripts.compare_runs A B` shows the cases that flipped. First run on `gpt-4o-mini` (3 runs per agent case, 2026-10-27): 14 of 14 pass, saved as `injection-baseline`.

## Layer 3: RAGAs

RAGAs is a Python library, and the backend is Python, so it runs in the same project.

Export: `cd sound-companion.server && uv run python -m scripts.export_run [--only q01,q02] [--mode vector|hybrid]` runs each `answer` question of `data/golden-set.json` through the real agent (the `agent_events` stream the UI reads, the configured retriever with the rewrite, one fresh thread per question) and saves `data/runs/<timestamp>.json`. Clarify and decline questions (q15 to q17) are left out and listed under `skipped`, because they have no contexts to score. Every model call goes to `usage_log`, and the run's cost is printed and saved.

Export format (`data/runs/<timestamp>.json`): the settings the run used (models, retriever mode, prompt hash, commit, golden set hash), `skipped`, `cost` and one entry per question:

```json
{
  "id": "q01",
  "question": "...",
  "answer": "...",
  "contexts": ["chunk text 1", "chunk text 2"],
  "tool_results": [{"name": "note_frequency", "args": {"note": "A4"}, "content": "{...}"}],
  "reference": "reference answer",
  "queries": ["query searched", "a rewrite"],
  "cost": 0.004,
  "error": null
}
```

`contexts` are the chunks the searches returned (from the `citations` events), each once. `tool_results` are the music tool calls (not searches), kept apart so the runner can pass them to RAGAs as contexts or leave them out (the decision of story 16). A run that failed keeps its entry with `error` set.

Runner: `cd sound-companion.server && uv run --with ragas==0.4.3 python -m eval.run_ragas data/runs/<timestamp>.json [--only q01,q02] [--tool-contexts] [--label L]` reads an export and prints faithfulness, answer relevancy, context precision (with reference) and context recall per question and overall (the mean of the questions that have a score, with how many that is). It uses the RAGAs 0.4 `metrics.collections` API with an OpenAI client pointed at OpenRouter. The judge is `OPENROUTER_JUDGE_MODEL` (default `google/gemini-2.5-flash-lite`, a different model family from the chat model so it does not grade its own answers, and cheap; a stronger judge is one setting away) and answer relevancy embeds with `OPENROUTER_EMBEDDING_MODEL`. RAGAs is in the optional dependency group `ragas`, so the app image (`uv sync --no-dev`) does not install it. Run it on demand, never in the request path. The scores are saved to `eval/results/<date>-ragas-<label>.json`.

- A question whose answer used no retrieved chunk (no `contexts`) gets answer relevancy only, and its faithfulness and context scores are `-` with the reason printed. Clarify questions never reach the runner, because the export leaves them out.
- A failed judge call loses that one score, not the run, and a failed agent run is not scored.
- `--tool-contexts none|faithfulness|all` says which metrics also count the music tool results (as text after the chunks). The default, `faithfulness`, is decision 72: tool results are grounding for faithfulness, but not retrieval for the context metrics. The targets below are checked against that default. `none` and `all` exist to compare.
- `scripts.compare_runs A B` compares two ragas runs: the mean of each metric, the questions whose score moved (at two decimals) and the settings that differ.
- Spend: the judge's HTTP responses are metered (`usage.cost`), the total is printed and one `usage_log` row per judge model is written with purpose `eval`.
- Packaging: `ragas` 0.4.3 fails to import against `langchain-community` 0.4 (`chat_models.vertexai` is gone), so `eval/judge.py` registers an empty stand-in module before importing it. Its dependency `instructor` also caps `jiter`, which lowers `openai` from 3.36.1 to 3.3.0 in the shared `uv.lock`. Tests pass on it, and it is the version the app image gets too.

Tool-only questions have no retrieved contexts, so score them with layers 1 and 2 and exclude them from the context metrics.

Metrics: faithfulness, answer relevancy, context precision, context recall.

Targets (course guidance): faithfulness 0.8 or above, context metrics 0.7 or above.

Caveats to document in the reflection:

- Faithfulness is strict. A correct claim from the model's own knowledge still lowers the score, so the system prompt says "answer only from retrieved context and tool results".
- Tool results are not retrieved context. Answers that rely on a tool result score lower on faithfulness unless the tool output is in the contexts passed to RAGAs. Decided in story 16 (decision 72): faithfulness gets chunks plus tool results, the context metrics get chunks only. First comparison on 22 questions: q06 faithfulness 0.67 to 1.00, q08 unscored to 0.69, means 0.83 (21 questions) and 0.84 (22). Only q06 and q08 used a tool, so the golden set cannot show a larger effect.
- Convention-conflict answers list several Conventions. Check that the judge does not penalise correct "sources differ" statements. Not settled by the first run: the exported q06 and q12 answers state no conflict between sources (q06 names C4 and the German H without comparing Conventions, q12 does not mention one), so there was no "sources differ" statement to judge. A case that makes the agent say it is needed.
- Low scores need a look at individual cases, not only the average.

## Reporting

The results sections below hold the metrics for vector-only vs hybrid, the RAGAs scores, the worst five questions, and what was changed in response. They feed the reflection part of the final pass.

## Results: RAGAs (story 16)

Run of 2026-10-28 on commit `9bf3863`: the 22 `answer` questions of `data/golden-set.json` (the plan said about 31, but 22 is what the golden set holds, and the three clarify questions q15 to q17 are left out of the export), answered by the chat model `openai/gpt-4o-mini` with the vector retriever and the rewrite on (decisions 63 and 71), scored by `google/gemini-2.5-flash-lite` with the default of decision 72. Files: export `data/runs/2026-10-28T09-14-47.json`, scores `eval/results/2026-10-28-ragas-final.json`. The hybrid retriever was not scored with RAGAs, since it is not the default (decision 71).

| Metric | Mean | Questions | Target | |
|---|---|---|---|---|
| Faithfulness | 0.84 | 22 | 0.8 | met |
| Context recall | 0.75 | 21 | 0.7 | met |
| Context precision | 0.47 | 21 | 0.7 | **missed** |
| Answer relevancy | 0.88 | 22 | none | |

q08 answers from a tool alone, so it has no retrieved chunks and no context scores. Six questions have faithfulness under 0.8 (q03, q04, q07, q10, q18, q23), and nine have precision under 0.5 (q01, q03, q05, q06, q07, q09, q10, q12, q19).

### Which low scores are the retrieval and which are the judge

The worst five questions by the mean of the three target metrics were scored again by a second judge (`openai/gpt-4o-mini`, `eval/results/2026-10-28-ragas-worst5-gpt-4o-mini.json`). A score that stays low under both judges is a real problem, one that changes a lot is the judge.

| Question | Gemini (faith / precision / recall) | GPT-4o-mini | Cause |
|---|---|---|---|
| q03 Hornbostel-Sachs classes, violin | 0.44 / 0.00 / 0.00 | 0.57 / 1.00 / 1.00 | Context scores: **judge**. All 6 chunks are from the right page, and one judge gives 0 for them. Faithfulness: **answer**. It lists five classes with examples (xylophones, synthesizers) that the chunks do not state, so both judges score it low. |
| q12 concert pitch vs written pitch | 0.89 / 0.00 / 0.33 | 0.67 / 0.00 / 1.00 | Precision: **retrieval**. Only 4 of 10 chunks are from the expected pages, and the first is a table row of Scientific pitch notation (`B \| 15.43385`), which precision, weighted by rank, punishes most. Recall: the judges disagree. |
| q10 trumpet vs cornet | 0.57 / 0.17 / 0.50 | 0.47 / 0.17 / 1.00 | Faithfulness: **answer**. "More compact and rounded", "trumpets are not used in brass bands" are not in the chunks. Precision: **retrieval**, 7 of 9 chunks are from Trumpet or Cornet but few are about the difference. |
| q07 authentic, half and plagal cadence | 0.65 / 0.00 / 0.67 | 0.75 / 0.14 / 1.00 | Precision: **retrieval**. 11 of 13 chunks are from the right pages, but many are other parts of Cadence (half-step cadences, frequency ratios, deceptive cadence). The right page is not enough, the section has to be right. |
| q19 mbira (alias) | 0.90 / 0.12 / 0.33 | 1.00 / 0.61 / 0.67 | **Both**. 4 of 8 chunks are not from Mbira, and the judges disagree by 0.5 on precision. |

Reading across the set:

- **Context precision is the real gap.** It is low under both judges for the questions where the chunks are noisy. The agent searches once per thing compared and the search tool merges the rewrites, so a question gets 5 to 16 chunks, and RAGAs counts every one, weighting the early ranks. Layer 1 (page-level precision@5, 0.87 for vector) hides this, since a chunk from the right page counts as relevant there.
- **Faithfulness misses come from the answers.** The model adds examples and facts from its own knowledge (q03, q10), which the faithfulness caveat above predicts. The system prompt already says "only from retrieved context", and `gpt-4o-mini` does not always follow it.
- **The judge is noisy.** `gemini-2.5-flash-lite` and `gpt-4o-mini` differ by up to 1.0 on a single question's precision or recall (q03). Means over 21 questions are usable, one question's score is not. Answer relevancy also moves a little on every run, because it generates and embeds questions.
- **Convention-conflict answers.** q06 and q12 do not state a conflict between sources, so the check that the judge does not penalise "sources differ" is still open (see the caveats). q12 faithfulness is 0.89 and q06 is 1.00 with tool results.
- **Tool results.** Decision 72.

### What was changed in response

Nothing in the bot yet. The evaluation was the story, and its findings are candidates for later stories, each to be measured with this runner against `ragas-final`:

1. Return fewer or better ordered chunks per search (a lower `k` or a rerank), against the precision gap.
2. Make the answer stay inside the chunks (a stricter prompt line, or a cheap check of the answer), against faithfulness misses like q03 and q10.
3. A stronger or second judge, or the same judge at several repeats, so that one question's score can be trusted. Costs about 0.05 credits a scoring now.
4. A golden question that makes the agent say sources differ, for the open Convention-conflict check.

### Experiment: 3 chunks per search (2026-10-29)

`SEARCH_K=3` instead of 5 (a new setting, default 5), same 22 questions, same judge. Files: export `data/runs/2026-10-29T09-47-45.json`, scores `eval/results/2026-10-29-ragas-k3.json`. Answering cost 0.017 credits and scoring 0.036.

| Metric | `ragas-final` (k=5) | k=3 | Target |
|---|---|---|---|
| Faithfulness | 0.84 | 0.79 | 0.8 |
| Answer relevancy | 0.88 | 0.89 | none |
| Context precision | 0.47 | 0.51 | 0.7 |
| Context recall | 0.75 | 0.72 | 0.7 |

Precision rose by 0.04 and still misses by a wide margin, recall fell by 0.03 and sits 0.02 over its target, and faithfulness fell under its target. The judge moves single questions by more than these differences (see above), so this is no clear gain and a visible cost. The default stays 5 (decision 76).

### Experiment: score cut and rerank (2026-10-29)

`SEARCH_RERANK=true` and `SEARCH_SCORE_RATIO=0.85`, `SEARCH_K=5`, `SEARCH_POOL=10`: each query fetches 10 candidates, chunks scoring under 85% of the best are dropped, and the rewrite model picks the chunks that help answer the question (`app/rag/rerank.py`), at most 5. Same 22 questions and judge. Files: export `data/runs/2026-10-29T10-13-30.json`, scores `eval/results/2026-10-29-ragas-rerank-cut.json`. Answering cost 0.022 credits (the rerank call is under 0.001 per question) and scoring 0.037.

| Metric | `ragas-final` | k=3 | rerank + cut | Target |
|---|---|---|---|---|
| Faithfulness | 0.84 | 0.79 | 0.83 | 0.8 |
| Answer relevancy | 0.88 | 0.89 | 0.89 | none |
| Context precision | 0.47 | 0.51 | **0.58** | 0.7 |
| Context recall | 0.75 | 0.72 | **0.78** | 0.7 |

Precision rose by 0.11 and recall by 0.03, with faithfulness still above its target. The rise is larger than the judge's noise on a mean of 21 questions, and it is the only one of the two trials that did not cost recall or faithfulness, so it is the default now (decision 77). Precision still misses 0.7. Questions still near zero: q07, q09 and q19 (mbira, recall 0.00 as well).

### Spend

All spend is in `usage_log`. The evaluation cost about **0.23 credits**, against the 1 credit target: the 22 answers (export, 0.020), and the judge (purpose `eval`, 0.206: two 2-question trials, four full scorings of the 22 answers, one of them with 5 scores lost to rate limits and run again, and the 5-question second judge). One full scoring with `gemini-2.5-flash-lite` costs about 0.045 credits and takes about 10 minutes, because the metrics run one after another. The embedding calls report no cost on OpenRouter.
