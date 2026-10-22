# Tool-calling eval: baseline and description fixes

Date: 2026-10-22. Issue 54 (Story 9). Saved runs: `sound-companion.server/eval/results/2026-10-22-tools-*.json`. Model `openai/gpt-4o-mini` (temperature 0), searches answered by the stub retriever, `data/golden-tools.json` with 20 cases. A run costs about 75k tokens. The saved files say `git: 430bc78`, and `430bc78 (uncommitted changes)` for the after run, because the prompt change was not yet committed when it ran.

## Results

| Run | Tool selection | Parameter accuracy (12 cases with arguments) | Medium selection |
|---|---|---|---|
| `tools-baseline` | 0.95 (19 of 20) | 1.00 | 0.83 |
| `tools-after-compare-rule` | 1.00 (20 of 20) | 1.00 | 1.00 |

Easy and hard cases were 1.00 in both runs. Compare them with `uv run python -m scripts.compare_runs eval/results/2026-10-22-tools-baseline.json eval/results/2026-10-22-tools-after-compare-rule.json`, which also shows the hashes of the prompt and of the `search_knowledge_base` description as the only things that changed.

## The one failing case and its fix

| Case | Baseline | Cause | Change |
|---|---|---|---|
| t13 "What separates a trumpet from a cornet?" (comparison) | one `search_knowledge_base("trumpet vs cornet")` instead of one search per instrument | Nothing told the model to search once per thing. A combined query is the known failure of Story 4 (q09: five Viola chunks, no Violin), so one search covers only one page. | System prompt rule 4 and the `search_knowledge_base` description now say to search once for each of two compared things. |

The worked example in the prompt uses the flute and the piccolo, not a golden-set subject (decision 56). A first version used the viola and the violin, which is case t12, so that run was discarded and the eval re-run.

## What this does not show

- It is one failure on 20 cases, and t12 and t14 passed the baseline without the rule, so the model was already inconsistent on comparisons. A single run at temperature 0 is not a repeated measure. A flip of one case is about the size of the run-to-run noise we have not measured.
- Parameter accuracy was 1.00 before any change, so there is nothing to fix there yet. The cases are mostly one-tool questions with clear wording, so the set is easy for the model.
- Searches return a stub, so the eval says nothing about whether the model searches again when real results are poor.

## Revisit

When the golden-tools file grows (ambiguous wording such as "written C" with no octave, two tools in one question), or the chat model changes (Story 9, issue 55), re-run and add the failures here.

## Model comparison (issue 55)

Same golden file (20 cases, `golden-tools.json` sha in each saved run), same prompt and tool descriptions (after the fix above), stub searches, one run per model. Prices are OpenRouter's public list on 2026-10-22, and each saved run stores the price it used. `gemini-2.5-flash-lite` is the only Gemini cheaper than `gpt-4o-mini`; `gemini-3.1-flash-lite` is the newest stable (non-preview) Flash-Lite.

| Model | Price in / out per 1M | Tool selection | Parameters | Tokens in + out | Cost of the 20 cases |
|---|---|---|---|---|---|
| `openai/gpt-4o-mini` | $0.15 / $0.60 | 1.00 | 1.00 | 72,629 + 1,905 | $0.0120 |
| `google/gemini-2.5-flash-lite` | $0.10 / $0.40 | 0.95 | 1.00 | 55,993 + 1,175 | $0.0061 |
| `google/gemini-3.1-flash-lite` | $0.25 / $1.50 | 0.85 | 1.00 | 78,579 + 1,489 | $0.0219 |

Runs: `eval/results/2026-10-22-tools-{gpt-4o-mini,gemini-2.5-flash-lite,gemini-3.1-flash-lite}.json`.

Failures:

- `gemini-2.5-flash-lite`: t12 (viola and violin) made 6 searches, one per aspect (size, tuning, role) of each instrument, instead of one per instrument.
- `gemini-3.1-flash-lite`: t13 made one combined search (the failure the prompt rule fixed for `gpt-4o-mini`), t14 made 3 searches (a combined one plus one per cadence), t16 repeated the same search.
- All three called the right tool with the right arguments whenever a tool was needed, and none called a tool in the no-tool cases. The model differences are all in how many searches a comparison gets.

What to keep in mind:

- The cases that differ are the three comparison and search ones, so the gap is about search counts, and the strict multiset rule counts an extra search as a failure even where the extra search is harmless. Whether the answers are as good (citations, clarifying questions, faithfulness) is not measured here.
- Two earlier `gemini-2.5-flash-lite` runs hit upstream HTTP 429 rate limits (7 cases, then 1) and were discarded. The script now prints a warning and does not save a run with errored cases. With the default retries of `ChatOpenAI`, this model is not reliable on OpenRouter's shared pool.
- One run per model on 20 cases: one case is 5 points.
- Cost here is only the agent calls. The whole 20-case set costs about 0.01 credits on `gpt-4o-mini`, so the cheaper model saves about 0.006 credits per 20 questions, far below the 1-credit target.
