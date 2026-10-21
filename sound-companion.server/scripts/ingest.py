"""Ingestion, stage one. Run from the server folder: `uv run python -m scripts.ingest`.

Fetches every Wikipedia entry of the Seed list into `data/cache/wikipedia/`. A re-run reads the
cache and makes no requests. Cleaning, the 5,000-character floor and storage come in later issues.
"""

import argparse
import json
from pathlib import Path

from app.rag.wikipedia import WikipediaCache, WikipediaFetcher

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_LIST = REPO_ROOT / "data" / "seed-list.json"
WIKIPEDIA_CACHE = REPO_ROOT / "data" / "cache" / "wikipedia"


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, help="only the first N entries of the Seed list")
    fetch_wikipedia(parser.parse_args().limit)
