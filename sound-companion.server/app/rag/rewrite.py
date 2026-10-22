"""Multi-query rewrite: a cheap model rephrases the user's query so retrieval catches other wordings
(synonyms, another Convention's name for the same thing). Never raises, a failure means no rewrites."""
import logging
from collections.abc import Callable

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app.rag.retriever import Filters, RetrievedChunk, Retriever

log = logging.getLogger(__name__)

MAX_REWRITES = 2

PROMPT = f"""Rewrite a search query for a music theory and instruments knowledge base (Wikipedia and a theory textbook).
Give {MAX_REWRITES} alternative queries that would match other pages or wordings of the same question: synonyms, \
the formal term, or another tradition's name (for example German note names). Make one of them name the broader subject the term belongs to (for example "written pitch" belongs to transposing instruments). Keep each short. Do not answer \
the question and do not add facts the query does not mention.

Query: {{query}}"""

Rewriter = Callable[[str], list[str]]


class Rewrites(BaseModel):
    queries: list[str] = Field(description=f"At most {MAX_REWRITES} alternative search queries.")


def make_rewriter(model: BaseChatModel, callbacks: list | None = None) -> Rewriter:
    """A function from a query to its rewrites (without the original), [] when the model fails or returns nothing.
    `callbacks` see the model call (an evaluation counts its tokens with them).
    Hook for Story 11: write this call to `usage_log` here."""
    structured = model.with_structured_output(Rewrites)

    def rewrite(query: str) -> list[str]:
        try:
            result = structured.invoke(PROMPT.format(query=query), config={"callbacks": callbacks or []})
            return clean_rewrites(query, result.queries)
        except Exception:  # any model or parsing failure falls back to the original query
            log.warning("query rewrite failed, searching with the original query", exc_info=True)
            return []

    return rewrite


def clean_rewrites(query: str, rewrites: list[str]) -> list[str]:
    """Trimmed, non-empty rewrites that differ from `query` and each other, at most MAX_REWRITES."""
    seen = {query.casefold()}
    kept = []
    for text in rewrites:
        text = (text or "").strip()
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            kept.append(text)
    return kept[:MAX_REWRITES]


def merge_results(results: list[list[RetrievedChunk]], k: int) -> list[RetrievedChunk]:
    """Interleave the result lists (best of each query first), drop repeated chunk ids and keep k overall,
    so every query contributes instead of the query with the highest scores crowding out the rest."""
    merged, seen = [], set()
    for rank in range(max((len(r) for r in results), default=0)):
        for chunks in results:
            if rank < len(chunks) and chunks[rank].id not in seen:
                seen.add(chunks[rank].id)
                merged.append(chunks[rank])
    return merged[:k]


def retrieve_with_rewrites(
    retriever: Retriever, rewriter: Rewriter | None, query: str, k: int, filters: Filters | None
) -> tuple[list[str], list[RetrievedChunk]]:
    """The queries searched (the original first) and the merged chunks, k overall."""
    queries = [query, *(rewriter(query) if rewriter else [])]
    return queries, merge_results([retriever.retrieve(q, k, filters) for q in queries], k)


class RewritingRetriever:
    """A `Retriever` that rewrites every query first, for the retrieval metrics. `queries_by_question`
    records what was searched for each query."""

    def __init__(self, retriever: Retriever, rewriter: Rewriter) -> None:
        self._retriever = retriever
        self._rewriter = rewriter
        self.queries_by_question: dict[str, list[str]] = {}

    def retrieve(self, query: str, k: int = 5, filters: Filters | None = None) -> list[RetrievedChunk]:
        queries, chunks = retrieve_with_rewrites(self._retriever, self._rewriter, query, k, filters)
        self.queries_by_question[query] = queries
        return chunks
