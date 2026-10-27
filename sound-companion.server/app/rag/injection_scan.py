"""Scan chunks for instruction-like strings (docs/SECURITY.md, ingestion). It only reports: nothing is deleted or edited.
The patterns are a first list, kept narrow so the report stays reviewable: it is a tripwire for planted text, not a filter."""
import re
from dataclasses import dataclass

from app.rag.chunking import Chunk
from app.tools.delimit import LOOKALIKE

SNIPPET_CONTEXT = 30  # characters kept on each side of a match
SNIPPET_MAX = 160

PATTERNS: dict[str, re.Pattern[str]] = {
    "ignore_previous": re.compile(r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+|your\s+)*(?:previous|prior|above|earlier|preceding)\b", re.I),
    "system_prompt": re.compile(r"\bsystem\s+(?:prompt|message|instructions?)\b", re.I),
    "role_override": re.compile(r"\byou\s+are\s+now\b|\bfrom\s+now\s+on,?\s+you\b", re.I),
    "new_instructions": re.compile(r"\bnew\s+instructions?\b", re.I),
    "reveal_prompt": re.compile(r"\b(?:reveal|print|repeat|show)\s+(?:me\s+)?(?:your|the)\s+(?:system\s+)?(?:prompt|instructions)\b", re.I),
    "role_marker": re.compile(r"^\s*(?:system|assistant)\s*:", re.I | re.M),
    "chat_token": re.compile(r"<\|[a-z_]+\|>|\[/?INST\]|<<SYS>>", re.I),
    "delimiter_lookalike": LOOKALIKE,
}


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    document_id: str
    title: str
    section: str
    pattern: str
    snippet: str


def snippet_of(text: str, start: int, end: int) -> str:
    snippet = text[max(0, start - SNIPPET_CONTEXT):end + SNIPPET_CONTEXT]
    return " ".join(snippet.split())[:SNIPPET_MAX]


def scan_chunk(chunk: Chunk) -> list[Hit]:
    """One hit per pattern that matches, with the first match as the snippet."""
    hits = []
    for name, pattern in PATTERNS.items():
        if match := pattern.search(chunk.content):
            hits.append(Hit(
                str(chunk.id), chunk.metadata["document_id"], chunk.metadata["title"], chunk.metadata["section"],
                name, snippet_of(chunk.content, match.start(), match.end()),
            ))
    return hits


def scan_chunks(chunks: list[Chunk]) -> list[Hit]:
    return [hit for chunk in chunks for hit in scan_chunk(chunk)]
