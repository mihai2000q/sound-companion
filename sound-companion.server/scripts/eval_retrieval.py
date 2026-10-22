"""Retrieval metrics on the golden set. Run from the server folder:
`uv run python -m scripts.eval_retrieval [-k 5] [--golden-set PATH]`.

Checks every expected source is a Corpus title or Alias, runs the retriever for each question and
prints precision@k and recall@k per question and overall. No model is called except to embed the
queries, which costs a fraction of a cent.
"""

import argparse
import sys
from pathlib import Path

import psycopg

from app.config import settings
from app.rag.evaluation import K, UnknownSourceError, check_sources, corpus_names, evaluate, load_golden_set, summarize
from app.rag.retriever import VectorRetriever

GOLDEN_SET = Path(__file__).resolve().parents[2] / "data" / "golden-set.json"


def main(k: int, golden_set: Path) -> int:
    questions = load_golden_set(golden_set)
    with psycopg.connect(settings.database_url) as connection:
        names = corpus_names([(t, a) for t, a in connection.execute("SELECT title, aliases FROM documents")])
    try:
        check_sources(questions, names)
    except UnknownSourceError as error:
        print(f"Golden set {golden_set.name}: {error}", file=sys.stderr)
        return 1

    retriever = VectorRetriever.from_settings()
    results = evaluate(retriever, questions, names, k)
    skipped = [q.id for q in questions if q.expected_behaviour != "answer" or not q.expected_sources]

    print(f"{'id':5} {'P@' + str(k):>5} {'R@' + str(k):>5}  question")
    for r in results:
        missing = [p for p in r.expected_pages if p not in r.found_pages]
        print(f"{r.id:5} {r.precision:5.2f} {r.recall:5.2f}  {r.question[:60]}"
              + (f"   missing: {', '.join(missing)}" if missing else ""))
    summary = summarize(results, k)
    print(f"\noverall over {summary.questions} questions (mean): precision@{k} {summary.precision:.3f}, "
          f"recall@{k} {summary.recall:.3f}")
    if skipped:
        print(f"skipped (no expected sources to find): {', '.join(skipped)}")
    print(f"cost {retriever.embedding_cost:.8f} credits (query embeddings only)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-k", type=int, default=K)
    parser.add_argument("--golden-set", type=Path, default=GOLDEN_SET)
    args = parser.parse_args()
    sys.exit(main(args.k, args.golden_set))
