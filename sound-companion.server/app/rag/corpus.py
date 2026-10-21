from dataclasses import dataclass, field
from datetime import datetime

from app.rag.documents import Document
from app.rag.omt import LICENSE as OMT_LICENSE
from app.rag.omt import OmtParse
from app.rag.wikipedia import WikipediaFetcher
from app.rag.wikipedia_clean import clean_wikipedia_html

WIKIPEDIA_LICENSE = "CC BY-SA 4.0"
MIN_CHARS = 5_000  # floor for Wikipedia articles (docs/DOMAIN.md, rule 3)

# Pages the tools and the Convention-conflict answers depend on (docs/DOMAIN.md, rules 2 and 6).
# Below the floor they are kept and flagged, not dropped.
REQUIRED_TITLES = {
    "Transposing instrument", "List of transposing instruments", "Concert pitch",
    "Harmonic series (music)", "Musical tuning", "Scientific pitch notation", "Musical note",
    "Organology", "Musical acoustics", "Chord notation", "Cadence", "Time signature",
}


@dataclass
class ReportLine:
    title: str
    detail: str


@dataclass
class WikipediaResult:
    included: list[Document] = field(default_factory=list)
    dropped: list[ReportLine] = field(default_factory=list)  # below the floor
    flagged: list[ReportLine] = field(default_factory=list)  # the author decides


def build_wikipedia_documents(entries: list[dict], fetcher: WikipediaFetcher) -> WikipediaResult:
    result = WikipediaResult()
    seen: dict[str, str] = {}  # canonical title -> the entry that claimed it
    for entry in entries:
        page = fetcher.fetch(entry["title"])
        if page.status == "missing":
            result.flagged.append(ReportLine(entry["title"], "page not found"))
            continue
        if page.canonical_title in seen:
            result.flagged.append(
                ReportLine(entry["title"], f"same page as the entry '{seen[page.canonical_title]}'")
            )
            continue
        cleaned = clean_wikipedia_html(fetcher.cache.html_path(entry["title"]).read_text("utf-8"))
        if cleaned.is_disambiguation:
            result.flagged.append(ReportLine(entry["title"], "disambiguation page, pick the article"))
            continue
        seen[page.canonical_title] = entry["title"]
        doc = Document(
            title=page.canonical_title,
            source_type=entry["source_type"],
            url=page.url,
            license=WIKIPEDIA_LICENSE,
            revision_id=str(page.revision_id),
            sections=cleaned.sections,
            topics=entry["topics"],
            aliases=_aliases(entry, page.canonical_title),
            fetched_at=datetime.fromisoformat(page.fetched_at),
        )
        if doc.char_count >= MIN_CHARS:
            result.included.append(doc)
        elif doc.title in REQUIRED_TITLES or entry["title"] in REQUIRED_TITLES:
            result.included.append(doc)
            result.flagged.append(
                ReportLine(doc.title, f"required page below the floor ({doc.char_count} chars), kept")
            )
        else:
            result.dropped.append(ReportLine(doc.title, f"{doc.char_count} chars"))
    return result


def _aliases(entry: dict, canonical_title: str) -> list[str]:
    """Seed aliases plus the name the entry used when Wikipedia redirected it."""
    names = [*entry["aliases"], entry["title"]]
    unique = dict.fromkeys(name for name in names if name != canonical_title)
    return list(unique)


def omt_documents(parse: OmtParse) -> list[Document]:
    return [
        Document(
            title=doc.title,
            source_type="textbook",
            url=doc.url,
            license=OMT_LICENSE,
            revision_id=doc.commit,
            sections=doc.sections,
        )
        for doc in parse.documents
    ]
