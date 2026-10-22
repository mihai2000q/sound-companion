"""Multi-query rewrite: a cheap model rephrases the user's query so retrieval catches other wordings
(synonyms, another Convention's name for the same thing). Never raises, a failure means no rewrites."""
import logging
from collections.abc import Callable

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app.rag.retriever import RetrievedChunk

log = logging.getLogger(__name__)

MAX_REWRITES = 2

PROMPT = f"""Rewrite a search query for a music theory and instruments knowledge base (Wikipedia and a theory textbook).
Give {MAX_REWRITES} alternative queries that would match other pages or wordings of the same question: synonyms, \
the formal term, or another tradition's name (for example German note names). Keep each short. Do not answer \
the question and do not add facts the query does not mention.

Query: {{query}}"""

Rewriter = Callable[[str], list[str]]


class Rewrites(BaseModel):
    queries: list[str] = Field(description=f"At most {MAX_REWRITES} alternative search queries.")


def make_rewriter(model: BaseChatModel) -> Rewriter:
    """A function from a query to its rewrites (without the original), [] when the model fails or returns nothing.
    Hook for Story 11: write this call to `usage_log` here."""
    structured = model.with_structured_output(Rewrites)

    def rewrite(query: str) -> list[str]:
        try:
            result = structured.invoke(PROMPT.format(query=query))
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
