"""Retrieval metrics against the golden set (docs/EVALUATION.md, layer 1). No model is called here:
the caller passes a `Retriever`, and the pieces are plain functions so they can be tested alone."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.rag.retriever import Filters, RetrievedChunk, Retriever

K = 5


@dataclass
class GoldenQuestion:
    id: str
    question: str
    category: str
    difficulty: str
    expected_sources: list[str]
    expected_behaviour: str = "answer"  # "answer", "clarify" or "decline"
    clarification_options: list[str] = field(default_factory=list)
    reference_answer: str = ""


@dataclass
class QuestionResult:
    id: str
    question: str
    precision: float
    recall: float
    expected_pages: list[str]  # canonical titles
    found_pages: list[str]  # the expected pages that appear in the top k
    retrieved: list[str]  # "Title > Section" of each returned chunk, best first


@dataclass
class Summary:
    k: int
    questions: int
    precision: float  # mean over the questions
    recall: float


class UnknownSourceError(ValueError):
    """Golden-set titles that are not a title or Alias of any stored document."""

    def __init__(self, unknown: dict[str, list[str]]) -> None:
        self.unknown = unknown
        lines = [f"  {title!r} (in {', '.join(ids)})" for title, ids in unknown.items()]
        super().__init__("not a Corpus title or Alias:\n" + "\n".join(lines))


def load_golden_set(path: Path) -> list[GoldenQuestion]:
    return [GoldenQuestion(**{k: v for k, v in entry.items() if k != "notes"})
            for entry in json.loads(path.read_text(encoding="utf-8"))]


def corpus_names(documents: list[tuple[str, list[str]]]) -> dict[str, str]:
    """Every title and Alias mapped to the canonical title of its document."""
    names: dict[str, str] = {}
    for title, aliases in documents:
        names[title] = title
    for title, aliases in documents:
        for alias in aliases:
            names.setdefault(alias, title)  # a real title wins over another page's Alias
    return names


def check_sources(questions: list[GoldenQuestion], names: dict[str, str]) -> None:
    """Raise `UnknownSourceError` naming every expected source or clarification option that is not
    in the Corpus, with the questions that use it."""
    unknown: dict[str, list[str]] = {}
    for q in questions:
        for title in [*q.expected_sources, *q.clarification_options]:
            if title not in names:
                unknown.setdefault(title, []).append(q.id)
    if unknown:
        raise UnknownSourceError(unknown)


def is_relevant(chunk: RetrievedChunk, expected: set[str]) -> bool:
    """A chunk is relevant if its title or one of its Aliases is an expected page."""
    return chunk.title in expected or any(alias in expected for alias in chunk.aliases)


def score(question: GoldenQuestion, chunks: list[RetrievedChunk], names: dict[str, str], k: int = K) -> QuestionResult:
    top = chunks[:k]
    # Alias and canonical title of one page count once, so expected pages are canonical titles.
    pages = list(dict.fromkeys(names[title] for title in question.expected_sources))
    expected = set(pages) | set(question.expected_sources)
    relevant = sum(is_relevant(chunk, expected) for chunk in top)
    found = [page for page in pages if any(is_relevant(c, {page}) for c in top)]
    return QuestionResult(
        id=question.id,
        question=question.question,
        precision=relevant / k,  # always out of k, so fewer than k results lowers it
        recall=len(found) / len(pages),
        expected_pages=pages,
        found_pages=found,
        retrieved=[f"{c.title} > {c.section or '(lead)'}" for c in top],
    )


def evaluate(
    retriever: Retriever,
    questions: list[GoldenQuestion],
    names: dict[str, str],
    k: int = K,
    filters: dict[str, Filters] | None = None,
) -> list[QuestionResult]:
    """Run every `answer` question through the retriever. `filters` maps a question id to the
    filters for it. Questions that expect a clarification or a decline have no sources to find and
    are skipped."""
    filters = filters or {}
    return [
        score(q, retriever.retrieve(q.question, k, filters.get(q.id)), names, k)
        for q in questions
        if q.expected_behaviour == "answer" and q.expected_sources
    ]


def summarize(results: list[QuestionResult], k: int = K) -> Summary:
    if not results:
        return Summary(k, 0, 0.0, 0.0)
    return Summary(
        k,
        len(results),
        sum(r.precision for r in results) / len(results),
        sum(r.recall for r in results) / len(results),
    )
