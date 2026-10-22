# Retrieval with and without query rewriting

Date: 2026-10-22. Issue 60 (Story 10). Saved runs: `sound-companion.server/eval/results/2026-10-22-vector-baseline.json` and `2026-10-22-vector-rewrite.json`. Same golden set (14 `answer` questions), same dense `VectorRetriever`, k=5. The rewrite run uses `scripts.eval_retrieval --rewrite`: each golden question is rewritten by `openai/gpt-4o-mini` into 2 extra queries, each query retrieves 5 chunks, and the results are interleaved, de-duplicated by chunk id and cut to 5 (`app/rag/rewrite.py`, the same code the search tool runs). Compare with `scripts.compare_runs`.

## Results

| Run | precision@5 | recall@5 | single-page (7), P / R | multi-page (7), P / R |
|---|---|---|---|---|
| `vector-baseline` | 0.814 | 0.821 | 0.829 / 1.000 | 0.800 / 0.643 |
| `vector-rewrite` | 0.829 | 0.893 | 0.829 / 1.000 | 0.829 / 0.786 |
| change | +0.014 | +0.071 | 0 / 0 | +0.029 / +0.143 |

Per question, only three changed: q01 (circle of fifths) recall 0.50 to 1.00, q12 (concert pitch) recall 0.50 to 1.00, q09 (viola and violin) precision 0.80 to 1.00. q06, q08 and q09's recall are unchanged.

## What it means for decision 55

Decision 55 predicted that rewriting would not fix multi-page recall. It partly does: multi-page recall rises from 0.643 to 0.786, and single-page questions are untouched (nothing got worse). But the gain is two questions out of seven (each +0.50 recall, +0.07 overall), so it is within the noise of a 14-question set, and the hard cases stay broken:

- q09: the rewrites ("Differences between viola and violin in dimensions, tuning, and function") still fill the top 5 with Viola chunks, Violin is missing.
- q06: the rewrites repeat the whole question, so Scientific pitch notation and Pitches and octave designations are still missing (recall 0.33).
- q08: Mode (music) is still missing.

The cause is the rewrite, not the idea: the model restates the question as a whole instead of splitting it by page. In the agent the tool loop already splits comparison questions into one search per thing (decision 60, rule 4), so this evaluation, which sends the whole question as one query, is the harder case. Per-page recall for q09 and q06 needs a cap on chunks per page or retrieval per entity, or hybrid search (Story 15), as decision 55 said.

## Cost

2,510 input and 378 output tokens for the 14 rewrites, about $0.0006 at the `gpt-4o-mini` prices ($0.15 / $0.6 per million), roughly $0.00004 per question, plus 3 times the query embeddings (0.00001 credits for the baseline run). A search costs about three embedding calls and one small chat call instead of one embedding call.

## Caveats

- 14 questions: one question moves recall by about 0.07.
- Rewriting runs at temperature 0 but the model is not guaranteed to repeat itself; the queries of this run are saved under `settings.rewrite.queries`.
- Relevance is by page title or Alias, as in [retrieval-baseline.md](retrieval-baseline.md).
