"""Rerank and cut: keep the chunks that answer the question, best first. Two steps, both optional.

`cut_by_score` is free: it drops chunks that score far below the best one. `make_reranker` asks a cheap model which
of the candidate chunks help answer the question, which attacks the real precision problem (the right page but the
wrong section). Neither raises: a failure keeps the chunks as they were."""
import logging
from collections.abc import Callable

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app.db.usage import UsageCallback
from app.rag.retriever import RetrievedChunk

log = logging.getLogger(__name__)

SNIPPET_CHARS = 500

PROMPT = """You choose passages for answering a question about music theory and instruments.
Below are numbered passages from a knowledge base (Wikipedia and a theory textbook). Pick the passages that help \
answer the question: the section has to be about what the question asks, a passage from the right page but about \
something else does not count, and neither does a bare table row. Give their numbers, best first. Leave out the rest. \
Do not answer the question.

Question: {query}

Passages:
{passages}"""

Reranker = Callable[[str, list[RetrievedChunk]], list[RetrievedChunk]]


class Ranking(BaseModel):
    relevant: list[int] = Field(description="Numbers of the passages that help answer the question, best first.")


def cut_by_score(chunks: list[RetrievedChunk], ratio: float) -> list[RetrievedChunk]:
    """Keep chunks scoring at least `ratio` times the best score. 0 keeps all. The best chunk always stays."""
    if ratio <= 0 or not chunks:
        return chunks
    best = max(chunk.score for chunk in chunks)
    return [chunk for chunk in chunks if chunk.score >= best * ratio]


def describe(index: int, chunk: RetrievedChunk) -> str:
    where = f"{chunk.title} > {chunk.section}" if chunk.section else chunk.title
    return f"[{index}] {where}\n{chunk.content[:SNIPPET_CHARS]}"


def pick(chunks: list[RetrievedChunk], numbers: list[int], keep: int) -> list[RetrievedChunk]:
    """The chunks the model named (1-based, unknown and repeated numbers ignored), at most `keep`. Empty when it named none."""
    chosen, seen = [], set()
    for number in numbers:
        if 1 <= number <= len(chunks) and number not in seen:
            seen.add(number)
            chosen.append(chunks[number - 1])
    return chosen[:keep]


def make_reranker(model: BaseChatModel, keep: int, callbacks: list | None = None) -> Reranker:
    """A function from the question and its candidate chunks to at most `keep` of them. When the model fails or
    names no usable chunk, the first `keep` candidates stay, so a search never comes back empty because of this step."""
    structured = model.with_structured_output(Ranking)

    def rerank(query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if len(chunks) <= 1:
            return chunks
        passages = "\n\n".join(describe(i, chunk) for i, chunk in enumerate(chunks, start=1))
        try:
            ranking = structured.invoke(
                PROMPT.format(query=query, passages=passages),
                config={"callbacks": [*(callbacks or []), UsageCallback("rerank")]},
            )
            return pick(chunks, ranking.relevant, keep) or chunks[:keep]
        except Exception:  # any model or parsing failure keeps the retrieval order
            log.warning("rerank failed, keeping the retrieval order", exc_info=True)
            return chunks[:keep]

    return rerank
