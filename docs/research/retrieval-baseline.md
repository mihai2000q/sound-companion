# Retrieval baseline on the golden set v0

Date: 2026-10-22. Issue 26 (Story 4). Saved runs: `sound-companion.server/eval/results/2026-10-22-*.json`. Dense search only (`VectorRetriever`, cosine, `openai/text-embedding-3-small`), k=5, 800-character chunks with 100 overlap, 7,329 chunks, golden set of 14 `answer` questions (17 entries, the 3 clarification entries have nothing to find). A run costs 0.000004 credits. The saved files say `git: 9fe42a6 (uncommitted changes)` because they were produced before this change was committed; the retrieval code was the one in that commit.

## Results

| Run | Filters | precision@5 | recall@5 |
|---|---|---|---|
| `vector-baseline` | none | 0.814 | 0.821 |
| `vector-topic-oracle` | any of the topics of each question's expected pages | 0.843 | 0.821 |
| `vector-topic-mismatch` | one topic none of the expected pages has (control) | 0.000 | 0.000 |

- **Filters do what they should.** The mismatch control returns only chunks of another topic, so nothing relevant appears and both metrics are 0. The oracle filter never hurts a question.
- **The oracle filter helps little.** It is an upper bound (the agent would have to guess the topics) and still adds only 0.029 precision: q06 (0.40 to 0.60) and q12 (0.80 to 1.00) improve, every other question is unchanged and recall does not move at all.

## Where retrieval fails

| Questions | recall@5 (mean) |
|---|---|
| 7 that need one page (q02 to q05, q11, q13, q14) | 1.000 |
| 7 that need two or three pages (q01, q06 to q10, q12) | 0.643 |

Every miss is a multi-page question where one page fills the top 5:

- q09 (viola and violin): the top 5 are all Viola chunks (and one Viol), Violin never appears, with or without the filter.
- q06 (middle C and German names): Musical note chunks take the slots, Scientific pitch notation and Pitches and octave designations are missing. The question mixes two topics (notes and notation), and three pages hold the answer.
- q01, q08, q12: the second page (Key signature, Mode (music), Transposing instrument) is outranked by chunks of the first page.

Precision is limited the same way: q13 (0.40) and q11 (0.60) return neighbouring pages (Electric guitar, other interval pages) next to the right one.

## Caveats

- 14 questions: one question moves recall by about 0.07, so differences below that are noise.
- The oracle filter uses the expected pages' own topics, which makes it generous. It says what a topic filter could add, not what the agent will manage.
- Relevance is by page title or Alias, so any chunk of the right page counts, whether or not the chunk answers the question.
