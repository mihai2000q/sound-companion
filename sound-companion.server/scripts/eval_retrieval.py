"""Retrieval metrics on the golden set. Run from the server folder:

    uv run python -m scripts.eval_retrieval [-k 5] [--golden-set PATH]
    uv run python -m scripts.eval_retrieval --label vector-baseline
    uv run python -m scripts.eval_retrieval --label vector-topic-oracle --filters topics-oracle

Checks every expected source is a Corpus title or Alias, runs the retriever for each question and
prints precision@k and recall@k per question and overall. With `--label` the run is saved to
`eval/results/<date>-<label>.json` (never overwritten), to compare later with `scripts.compare_runs`.
`--filters` restricts each question by its expected pages' topics, see `derive_filters`.
No model is called except to embed the queries, which costs a fraction of a cent.
"""

import argparse
import hashlib
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import psycopg

from app.config import settings
from app.rag.chunking import CHUNK_CHARS, OVERLAP_CHARS
from app.rag.eval_results import build_run, save_run
from app.rag.evaluation import (
    K, UnknownSourceError, check_sources, corpus_names, derive_filters, evaluate, load_golden_set, summarize,
)
from app.rag.retriever import VectorRetriever
from app.rag.vector_store import HnswIterative

GOLDEN_SET = Path(__file__).resolve().parents[2] / "data" / "golden-set.json"


def git_state() -> str:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()

    return git("rev-parse", "--short", "HEAD") + (" (uncommitted changes)" if git("status", "--porcelain") else "")


def main(k: int, golden_set: Path, label: str | None, filter_mode: str) -> int:
    questions = load_golden_set(golden_set)
    with psycopg.connect(settings.database_url) as connection:
        documents = connection.execute("SELECT title, aliases, topics FROM documents").fetchall()
        chunk_count = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
    names = corpus_names([(title, aliases) for title, aliases, _ in documents])
    topics_by_title = {title: [t for t in topics.split("|") if t] for title, _, topics in documents}
    try:
        check_sources(questions, names)
    except UnknownSourceError as error:
        print(f"Golden set {golden_set.name}: {error}", file=sys.stderr)
        return 1

    filters = derive_filters(questions, names, topics_by_title, filter_mode)
    retriever = VectorRetriever.from_settings()
    results = evaluate(retriever, questions, names, k, filters)
    skipped = [q.id for q in questions if q.expected_behaviour != "answer" or not q.expected_sources]

    print(f"{'id':5} {'P@' + str(k):>5} {'R@' + str(k):>5}  question")
    for r in results:
        missing = [p for p in r.expected_pages if p not in r.found_pages]
        print(f"{r.id:5} {r.precision:5.2f} {r.recall:5.2f}  {r.question[:60]}"
              + (f"   missing: {', '.join(missing)}" if missing else ""))
    summary = summarize(results, k)
    print(f"\noverall over {summary.questions} questions (mean): precision@{k} {summary.precision:.3f}, "
          f"recall@{k} {summary.recall:.3f}   [filters: {filter_mode}]")
    if skipped:
        print(f"skipped (no expected sources to find): {', '.join(skipped)}")
    print(f"cost {retriever.embedding_cost:.8f} credits (query embeddings only)")

    if label:
        run = build_run(
            label,
            {
                "retriever": "VectorRetriever (dense, cosine)",
                "k": k,
                "filters": filter_mode,
                "embedding_model": settings.openrouter_embedding_model,
                "chunking": {
                    "splitter": f"RecursiveCharacterTextSplitter (langchain-text-splitters {version('langchain-text-splitters')})",
                    "chunk_chars": CHUNK_CHARS, "overlap_chars": OVERLAP_CHARS,
                },
                "index_query_options": HnswIterative().to_string(),
                "corpus": {"documents": len(documents), "chunks": chunk_count},
                "golden_set": {
                    "file": golden_set.name,
                    "entries": len(questions),
                    "sha256": hashlib.sha256(golden_set.read_bytes()).hexdigest()[:12],
                },
                "git": git_state(),
            },
            summary,
            results,
            {qid: {"topics": list(f.topics), "match": f.topic_match} for qid, f in filters.items()},
        )
        print(f"saved {save_run(run).relative_to(Path.cwd())}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-k", type=int, default=K)
    parser.add_argument("--golden-set", type=Path, default=GOLDEN_SET)
    parser.add_argument("--label", help="save the run under this label")
    parser.add_argument("--filters", choices=["none", "topics-oracle", "topics-mismatch"], default="none")
    args = parser.parse_args()
    sys.exit(main(args.k, args.golden_set, args.label, args.filters))
