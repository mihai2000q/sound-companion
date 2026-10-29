# Reflection

What works, what does not, and what to do next, based on the saved runs in `sound-companion.server/eval/results/` and `data/runs/`. Numbers are from the 22 retrieval questions of `data/golden-set.json` and the 22 cases of `data/golden-tools.json` unless said otherwise. Decision numbers refer to [DECISIONS.md](DECISIONS.md), the full tables to [EVALUATION.md](EVALUATION.md).

## What the evaluation shows

| Layer | Result | Target |
|---|---|---|
| Retrieval, page level (vector, k=5) | precision@5 0.873, recall@5 0.886 (`vector-baseline-25q`) | none set |
| Tool calling (`gpt-4o-mini`, 22 cases) | selection 0.91, parameters 1.00 (the 20 original cases 1.00; the two clarification cases t21 and t22 fail) | none set |
| Injection (agent cases, 3 runs each) | all pass | all pass |
| RAGAs faithfulness | 0.83 with the rerank (0.84 before) | 0.8, met |
| RAGAs context recall | 0.78 with the rerank (0.75 before) | 0.7, met |
| RAGAs context precision | 0.58 with the rerank and score cut (0.47 before, `ragas-final`) | 0.7, **missed** |

The evaluation as a whole cost about 0.23 credits against the 1 credit target, and one demo run costs about 0.006.

## Known problems, with cause and evidence

**1. q06 never shows the Helmholtz name c′ (decision 73).**
- Cause: the agent calls `note_frequency(C4)` and searches only "B-flat and B natural in German". Those chunks contain no c′. A search for "middle C Helmholtz" does return the right chunk (Musical note > Distinguishing pitches of different octaves), so retrieval is not the cause, the agent never makes that search.
- Evidence: 0 of 9 runs after four rule 9 wordings, and 0 of 3 each with hybrid retrieval, `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gpt-4.1-mini`, a changed tool description and a worked example in the history. q06 context recall is 0.33 in the RAGAs run.
- Status: the check was relaxed to C4, German B and H, each with a Citation, and "the names differ". It is still flaky: `scripts.check_conventions --runs 3` on 2026-10-28 gave q06 1 of 3 (the other runs missed the middle C Citation or the C4 name) and q12 3 of 3.

**2. Convention-conflict answers do not say that sources differ.**
- Evidence: the exported q06 and q12 answers name the Conventions without comparing them, so the RAGAs check that the judge does not punish "sources differ" statements has nothing to judge. Still open in the caveats of EVALUATION.md.

**3. Context precision 0.47 (target 0.7).**
- Cause: mostly retrieval, the right page but the wrong section. A comparison question searches once per thing compared, the search tool merges the rewrites, and a question gets 5 to 16 chunks, all of which RAGAs counts, weighted by rank.
- Evidence: nine questions under 0.5 (q01, q03, q05, q06, q07, q09, q10, q12, q19). In the second-judge check, q12 (first chunk is a table row of Scientific pitch notation), q10 and q07 (11 of 13 chunks from Cadence, many from other sections) stayed low under both judges. Page-level precision@5 (0.873) hides this, because a chunk from the right page counts as relevant there.

**4. Faithfulness misses where the answer adds its own knowledge.**
- Evidence: six questions under 0.8 (q03, q04, q07, q10, q18, q23). q03 lists five classes with examples the chunks do not state, q10 says "more compact and rounded" and "trumpets are not used in brass bands". Both judges score them low. The prompt already says "only from retrieved context", and `gpt-4o-mini` does not always follow it. The mean still meets the target, so this is a tail problem.

**5. Underspecified questions are answered, not clarified.**
- Evidence: on 2026-10-28 "Tell me about the guitar." and "What is the range of a saxophone?" both got full answers after several searches, although the golden set expects a clarifying question (q15, q16, decision 54). Decision 56 fixed exactly these two questions with worked examples in the prompt, and named its own revisit condition ("the clarify cases fail again"). Only the no-context case ("Transpose it up a fifth.", also t20 in the tool set) still asks.
- Why it went unnoticed: the retrieval eval skips q15 to q17 and the RAGAs export leaves them out. Since 2026-10-29 the tool eval has both questions as t21 and t22 and fails them (the agent calls `search_knowledge_base`), so the regression is now measured. The revisit condition of decision 56 is met, the fix is still open.

**6. The judge is noisy.**
- Evidence: `gemini-2.5-flash-lite` and `gpt-4o-mini` differ by up to 1.0 on one question's precision or recall (q03: 0.00 against 1.00 for the same six chunks from the right page). Means over 21 questions are usable, one question's score is not. A full scoring costs about 0.045 credits and takes about 10 minutes.

**7. (Fixed 2026-10-29, decision 78) The `ragas` dependency group lowered `openai` in the shared lock.**
- Cause: `ragas` 0.4.3 depends on `instructor`, which caps `jiter`, so the one lock file had `openai` 3.3.0 and `jiter` 0.14.0, and the app image got them too although it never imports `ragas`.
- Fix: the group is gone and `ragas` runs with `uv run --with ragas==0.4.3`, so the lock has `openai` 3.41.0 and `jiter` 0.18.0 and the evaluation gets its own older copies for that one run. `ragas` still fails to import against `langchain-community` 0.4 (`chat_models.vertexai` is gone), so `eval/judge.py` registers an empty stand-in module first.

**Smaller limits**
- The tool answers carry their source as text, not as citation chips, because chips come only from retrieved chunks.
- Not done, by design (SECURITY.md): no classifier-based injection detection, no authentication, no audit of the Corpus beyond samples and the instruction-string scan (0 hits in 7,329 chunks), no analysis of share-alike questions for generated answers.
- Retrieval choice: hybrid search alone equals vector on exact-term and alias questions, and hybrid with rewrite has the best recall (0.932) but the worst precision (0.773). Vector with rewrite stayed the default (decision 71).

## Improvement ideas, ranked

1. **Let the rewrite step see the whole question (decision 73).** Cheapest change with the widest reach: it can add a "middle C naming systems" query, which would restore the c′ check for q06 and probably help every question where the agent's single tool query drops half of the user's wording. Measure with `check_conventions` and `eval_retrieval --rewrite`.
2. **Fix the clarify cases, now that they are tested.** A requirement (decision 54) that has regressed. t21 and t22 in the tool-calling set (expected: no search) fail, so a prompt change is measured. Try more worked examples, as in decision 56, or a stronger model.
3. **Better-ordered chunks per search (done in part: a lower `k` alone did not work, the rerank and score cut lifted precision to 0.58, decision 77).** The only missed target. Tried `k=3` on 2026-10-29: precision 0.51, recall 0.72, faithfulness 0.79, so no clear gain and faithfulness fell under its target (decision 76). What is left is a rerank, or dropping table rows, since the problem is the wrong section of the right page. Measure with the RAGAs runner against `ragas-final`, and keep an eye on recall, which already sits just above its target (0.75 against 0.7).
4. **A "sources differ" golden case.** Closes the open judge check, and it needs idea 1 first, because today no answer states a conflict.
5. **A stricter "stay inside the chunks" rule**, or a cheap check of the answer. Ranked below precision because faithfulness already meets its target and the misses are a tail of single questions.
6. **A steadier judge.** A second judge, or the same one at several repeats, so one question's score can be trusted. It changes how well we measure, not what the bot does, and costs about 0.05 credits per scoring.
