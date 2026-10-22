from dataclasses import dataclass, field
from typing import Literal, Protocol

from langchain_postgres import PGVectorStore

from app.rag.embeddings import OpenRouterEmbeddings
from app.rag.filters import combine, topic_filter
from app.rag.vector_store import open_store

SOURCE_TYPES = ("encyclopedia", "textbook")


@dataclass(frozen=True)
class Filters:
    """Narrow a search. Every field is optional and the given ones are ANDed."""

    source_type: Literal["encyclopedia", "textbook"] | None = None
    topics: tuple[str, ...] = ()
    topic_match: Literal["any", "all"] = "all"  # how `topics` combine
    title: str | None = None  # a document's canonical title, exact match

    def __post_init__(self) -> None:
        if self.source_type is not None and self.source_type not in SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {SOURCE_TYPES}, got {self.source_type!r}")
        if self.topic_match not in ("any", "all"):
            raise ValueError(f"topic_match must be 'any' or 'all', got {self.topic_match!r}")


@dataclass
class RetrievedChunk:
    """A chunk with what a Citation needs. `score` is similarity, higher is better."""

    id: str
    content: str  # as embedded: the title and Alias line, then the text
    score: float
    title: str
    section: str  # heading path, "" for the lead
    url: str
    license: str
    revision_id: str
    source_type: str
    topics: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


class Retriever(Protocol):
    """What the agent's search tool and the metrics script call. The baseline is `VectorRetriever`,
    hybrid search (Story 15) is another implementation behind the same method."""

    def retrieve(self, query: str, k: int = 5, filters: Filters | None = None) -> list[RetrievedChunk]: ...


class VectorRetriever:
    """Dense search over the chunk store with cosine similarity."""

    def __init__(self, store: PGVectorStore, embeddings: OpenRouterEmbeddings | None = None) -> None:
        self._store = store
        self._embeddings = embeddings

    @classmethod
    def from_settings(cls) -> "VectorRetriever":
        from app.config import settings

        embeddings = OpenRouterEmbeddings(
            settings.openrouter_api_key, settings.openrouter_base_url, settings.openrouter_embedding_model
        )
        return cls(open_store(embeddings), embeddings)

    @property
    def embedding_cost(self) -> float:
        """Credits spent embedding queries so far, 0 when the embeddings do not report cost."""
        return getattr(self._embeddings, "cost", 0.0)

    def retrieve(self, query: str, k: int = 5, filters: Filters | None = None) -> list[RetrievedChunk]:
        results = self._store.similarity_search_with_score(query, k=k, filter=to_filter(filters))
        return [to_chunk(document, distance) for document, distance in results]


def to_filter(filters: Filters | None) -> dict | None:
    """The store's filter for `filters`, None when it narrows nothing."""
    if filters is None:
        return None
    return combine(
        topic_filter(list(filters.topics), filters.topic_match) if filters.topics else None,
        {"title": filters.title} if filters.title else None,
        {"source_type": filters.source_type} if filters.source_type else None,
    )


def to_chunk(document, distance: float) -> RetrievedChunk:
    meta = document.metadata
    return RetrievedChunk(
        id=str(document.id),
        content=document.page_content,
        score=1 - distance,  # the store returns cosine distance, lower is better
        title=meta["title"],
        section=meta["section"],
        url=meta["url"],
        license=meta["license"],
        revision_id=meta["revision_id"],
        source_type=meta["source_type"],
        topics=[t for t in meta["topics"].split("|") if t],
        aliases=[a for a in meta["aliases"].split("|") if a],
    )
