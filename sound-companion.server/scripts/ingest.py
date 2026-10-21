"""Ingestion, stage one. Run from the server folder: `uv run python -m scripts.ingest`.

Fetches every Wikipedia entry of the Seed list into `data/cache/wikipedia/`, clones Open Music
Theory v1 into `data/cache/omt/`, cleans both into documents, applies the 5,000-character floor to
Wikipedia articles, prints a report and stores the documents. A re-run reads the caches and makes
no requests. Chunking and embedding come in Story 3.
"""

import argparse
import json
from pathlib import Path

from app.rag.corpus import MIN_CHARS, build_wikipedia_documents, omt_documents
from app.rag.omt import clone_omt, parse_omt
from app.rag.wikipedia import WikipediaCache, WikipediaFetcher

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_LIST = REPO_ROOT / "data" / "seed-list.json"
WIKIPEDIA_CACHE = REPO_ROOT / "data" / "cache" / "wikipedia"
OMT_CLONE = REPO_ROOT / "data" / "cache" / "omt"


def main(limit: int | None, dry_run: bool) -> None:
    entries = [e for e in json.loads(SEED_LIST.read_text()) if e["source_type"] == "encyclopedia"]
    if limit is not None:
        entries = entries[:limit]
    fetcher = WikipediaFetcher(WikipediaCache(WIKIPEDIA_CACHE))
    wikipedia = build_wikipedia_documents(entries, fetcher)

    commit = clone_omt(OMT_CLONE)
    omt = parse_omt(OMT_CLONE, commit)
    textbook = omt_documents(omt)

    print(f"Wikipedia: {len(entries)} entries, {fetcher.requests_made} requests made")
    print(f"\nINCLUDED  {len(wikipedia.included)} Wikipedia articles, {len(textbook)} OMT pages (commit {commit[:7]})")
    for doc in wikipedia.included:
        redirected = f" (also: {', '.join(doc.aliases)})" if doc.aliases else ""
        print(f"  {doc.title}: {doc.char_count} chars, rev {doc.revision_id}{redirected}")
    print(f"\nDROPPED   {len(wikipedia.dropped)} below the {MIN_CHARS}-character floor")
    for line in wikipedia.dropped:
        print(f"  {line.title}: {line.detail}")
    print(f"\nFLAGGED   {len(wikipedia.flagged)} for the author to decide")
    for line in wikipedia.flagged:
        print(f"  {line.title}: {line.detail}")
    print(f"\nOMT EXCLUDED  {len(omt.excluded)} files")
    for slug, reason in omt.excluded.items():
        print(f"  {slug}: {reason}")

    if limit is not None or dry_run:
        print("\nNothing stored (--limit or --dry-run).")
        return
    from app.config import settings  # only here, so a dry run needs no environment
    from app.rag.store import store_documents

    stored, removed = store_documents(settings.database_url_async, [*wikipedia.included, *textbook])
    print(f"\nStored {stored} documents, removed {removed} stale.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, help="first N Wikipedia entries only, stores nothing")
    parser.add_argument("--dry-run", action="store_true", help="report only, do not store")
    args = parser.parse_args()
    main(args.limit, args.dry_run)
