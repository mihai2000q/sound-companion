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
