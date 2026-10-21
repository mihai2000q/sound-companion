from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Section:
    heading_path: list[str]
    text: str


@dataclass
class Document:
    """One Corpus document, ready to store. Sections keep the heading path for Story 3's chunker."""

    title: str
    source_type: str  # "encyclopedia" or "textbook"
    url: str
    license: str
    revision_id: str  # Wikipedia revision id, or the git commit for the textbook
    sections: list[Section]
    topics: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    fetched_at: datetime | None = None

    @property
    def char_count(self) -> int:
        return sum(len(section.text) for section in self.sections)
