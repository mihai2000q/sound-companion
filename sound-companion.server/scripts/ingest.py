"""Ingestion, stage one. Run from the server folder: `uv run python -m scripts.ingest`.

Fetches every Wikipedia entry of the Seed list into `data/cache/wikipedia/`, and clones Open Music
Theory v1 into `data/cache/omt/` and parses it. A re-run reads the caches and makes no requests.
The 5,000-character floor and storage come in a later issue.
"""

import argparse
import json
from pathlib import Path

from app.rag.omt import clone_omt, parse_omt
from app.rag.wikipedia import WikipediaCache, WikipediaFetcher

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_LIST = REPO_ROOT / "data" / "seed-list.json"
WIKIPEDIA_CACHE = REPO_ROOT / "data" / "cache" / "wikipedia"
OMT_CLONE = REPO_ROOT / "data" / "cache" / "omt"


def fetch_wikipedia(limit: int | None) -> None:
    entries = [e for e in json.loads(SEED_LIST.read_text()) if e["source_type"] == "encyclopedia"]
    if limit is not None:
        entries = entries[:limit]
    fetcher = WikipediaFetcher(WikipediaCache(WIKIPEDIA_CACHE))
    for entry in entries:
        page = fetcher.fetch(entry["title"])
        if page.status == "missing":
            print(f"MISSING   {page.requested_title}")
        elif page.redirect_alias:
            print(f"redirect  {page.requested_title} -> {page.canonical_title} (rev {page.revision_id})")
        else:
            print(f"ok        {page.canonical_title} (rev {page.revision_id})")
    print(f"{len(entries)} entries, {fetcher.requests_made} requests made")


def parse_open_music_theory() -> None:
    commit = clone_omt(OMT_CLONE)
    result = parse_omt(OMT_CLONE, commit)
    for doc in result.documents:
        words = sum(len(s.text.split()) for s in doc.sections)
        print(f"ok        {doc.slug} ({len(doc.sections)} sections, {words} words)")
    for slug, reason in result.excluded.items():
        print(f"EXCLUDED  {slug}: {reason}")
    print(f"{len(result.documents)} documents, {len(result.excluded)} excluded, commit {commit[:7]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=["wikipedia", "omt", "all"], default="all")
    parser.add_argument("--limit", type=int, help="Wikipedia only: the first N entries of the Seed list")
    args = parser.parse_args()
    if args.source in ("wikipedia", "all"):
        fetch_wikipedia(args.limit)
    if args.source in ("omt", "all"):
        parse_open_music_theory()
