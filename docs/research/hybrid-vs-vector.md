# Hybrid search against the vector baseline

Date: 2026-10-27. Issue 89 (Story 15). Saved runs: `sound-companion.server/eval/results/2026-10-27-{vector-baseline,vector-rewrite,hybrid,hybrid-rewrite}-25q.json`. k=5, 7,329 chunks, `openai/text-embedding-3-small`, rewrite model `openai/gpt-4o-mini`, golden set of 22 `answer` questions (25 entries, 3 clarify, 8 of them added in issue 88). All four runs use the same golden set (same hash), so they compare. `HybridRetriever` is dense top 20 plus keyword top 20 (`websearch_to_tsquery`), fused with RRF (constant 60).

## Results

| Run | precision@5 | recall@5 | single-page P / R (15) | multi-page P / R (7) | exact-term and alias P / R (11) |
|---|---|---|---|---|---|
| `vector-baseline-25q` | 0.873 | 0.886 | 0.907 / 1.000 | 0.800 / 0.643 | 0.927 / 1.000 |
| `hybrid-25q` | 0.864 | 0.886 | 0.907 / 1.000 | 0.771 / 0.643 | 0.927 / 1.000 |
| `vector-rewrite-25q` | 0.818 | 0.909 | 0.813 / 1.000 | 0.829 / 0.714 | 0.800 / 1.000 |
| `hybrid-rewrite-25q` | 0.773 | 0.932 | 0.773 / 1.000 | 0.771 / 0.786 | 0.782 / 1.000 |

"Exact-term and alias" is the 11 questions with category `exact-term` (q04, q21, q22, q23) or `alias` (q05, q13, q18, q19, q20, q24, q25). Reproduce any row pair with `uv run python -m scripts.compare_runs eval/results/2026-10-27-vector-baseline-25q.json eval/results/2026-10-27-<run>.json` (it prints the groups).

## What it shows

- **Hybrid alone is a wash.** Exact-term and alias questions have the same group means (precision 0.927, recall 1.000), but only because q13 (+0.20 precision) cancels q05 (-0.20), single-page questions are equal, and overall precision moves by -0.009. Recall does not change. Five questions changed: q13 precision +0.20, q12 recall +0.50, q01 precision -0.20, q05 precision -0.20, q10 recall -0.50.
- **The exact-term questions cannot separate the modes.** Every one of them already has recall 1.000 under dense search. Each chunk starts with its title and Alias line, so the vectors already know "English horn", "Rhodes piano" or "Stuttgart pitch". Hybrid has nothing to rescue on this Corpus.
- **The keyword half is often empty.** `websearch_to_tsquery` ANDs the words left after stop words, and these are full questions. 8 of the 22 questions match no chunk at all (q03, q06 to q09, q11, q14, q21), and q02 matches one, so for them hybrid is the dense search. Short alias queries do match (q24 79 chunks, q23 28, q04 27), and that is where the keyword half could matter, but dense already finds the page.
- **Rewriting is the larger effect, and it costs precision.** With either retriever it raises recall (vector 0.886 to 0.909, hybrid 0.886 to 0.932) and lowers precision (vector -0.055, hybrid -0.100). The loss is on exact-term and alias questions: the rewrites add generic queries ("String instruments of the Renaissance" for q24, "Electric piano history" for q18) whose chunks displace chunks of the right page.
- **Hybrid with rewrite has the best recall and the worst precision.** Against `vector-rewrite-25q` (what the agent does today, decision 63) it gains 0.023 recall, all of it multi-page (0.714 to 0.786, one question, q01), and loses 0.045 precision.

## Which questions got worse, and why

- **q10 (trumpet and cornet), recall 1.00 to 0.50 without rewrite.** The keyword half has 3 matches, all about the cornet, so RRF puts Cornet chunks in every slot and Trumpet drops out. Dense search had the Trumpet chunk at rank 4. This is the page-dominance problem of the baseline, made a little worse. The rewrite brings Trumpet back.
- **q05 (cor anglais), precision 1.00 to 0.80.** One Oboe chunk, found only by the dense half, takes the fifth slot. RRF is rank-only, so a rank-1 hit from either half scores the same and the keyword half's four matches do not push it out. Same effect as noted in `DATABASE-SCHEMA.md`.
- **q01 (circle of fifths and key signatures), precision 0.80 to 0.60.** Seven chunks match the keywords. They are neighbours (Relative key, Key signatures) that rank well on word overlap, not the page the question needs.
- **q22, q24 and the other alias questions under rewrite** lose precision in both vector and hybrid runs, so that is the rewrite, not the fusion.

## Cost

About 0.002 credits for all the runs of this issue, nearly all of it the rewrite model: each rewrite run is about 3,900 input and 550 output tokens ($0.0009) and its query embeddings 0.000014 credits, a run without rewrite costs 0.0000055 credits of query embeddings. No answer-model calls.

## Caveats

- 22 questions, 11 of them in one group: one question moves recall by about 0.045 overall and by 0.14 within the multi-page group. The multi-page gain of hybrid with rewrite is one question.
- The golden set has no question where the vectors fail on a rare term. Such a case (a rare abbreviation or a spelling the embedding does not capture) would be the fair test of the keyword half, and this Corpus and question set did not produce one.
- Only weight 1:1 and RRF constant 60 were tried, with `websearch_to_tsquery` and the `english` configuration.
