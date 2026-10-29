from collections.abc import Callable
from typing import Annotated, Literal

from langchain_core.tools import StructuredTool
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field, ValidationError

from app.rag.rerank import Reranker
from app.rag.retriever import Filters, RetrievedChunk, Retriever
from app.rag.rewrite import Rewriter, retrieve_with_rewrites
from app.tools.delimit import wrap_document

NOT_FOUND = (
    "Nothing relevant found in the knowledge base for this query. "
    "Say so to the user and do not answer from memory."
)

DESCRIPTION = """Search the music knowledge base (Wikipedia articles and the Open Music Theory textbook) \
for explanations and facts about music theory and instruments. Returns text chunks, each with its page \
title, section, URL, licence and a similarity score. Cite the page and section of every fact you use.

Use it for: what a concept is, how an instrument works, history, terminology, and which pages exist on \
a subject (for example to list the kinds of guitar before asking the user which one they mean).
To compare two things, call it once for each thing, not once with both names in the query.
Do NOT use it for calculations (notes in a chord or scale, intervals, transposition, frequencies), which \
need the music tools, or for requests outside music theory and instruments.

Filters are optional and narrow the search; leave them out unless the user asks for them or a first \
search returned the wrong pages. `title` is a page's exact title, for example "Cor anglais"."""


class SearchInput(BaseModel):
    query: Annotated[str, Field(description="What to look for, as a short natural-language question or phrase.")]
    source_type: Annotated[
        Literal["encyclopedia", "textbook"] | None,
        Field(description="Only 'encyclopedia' (Wikipedia) or only 'textbook' (Open Music Theory)."),
    ] = None
    topic: Annotated[str | None, Field(description="Only pages tagged with this topic, for example 'woodwinds'.")] = None
    title: Annotated[str | None, Field(description="Only the page with this exact title, for example 'Cor anglais'.")] = None


def format_chunk(chunk: RetrievedChunk) -> str:
    location = f"{chunk.title} > {chunk.section}" if chunk.section else chunk.title
    header = f"[{location}] url: {chunk.url} | license: {chunk.license} | score: {chunk.score:.3f}"
    return wrap_document(location, f"{header}\n{chunk.content}")


def citation_item(chunk: RetrievedChunk) -> dict:
    """Stored metadata only, never model text. `id` lets the UI match a chip to a chunk, `content` feeds the inspector."""
    return {
        "id": chunk.id,
        "title": chunk.title,
        "section": chunk.section,
        "url": chunk.url,
        "score": chunk.score,
        "license": chunk.license,
        "content": chunk.content,
    }


def stream_writer() -> Callable[[dict], None]:
    """The run's custom-event writer. Outside an agent run (a direct call, a script) there is none, so events are dropped."""
    try:
        return get_stream_writer()
    except (RuntimeError, KeyError):  # no run: RuntimeError on older langgraph, KeyError for a missing runtime
        return lambda event: None


def search_knowledge_base(
    retriever: Retriever,
    query: str,
    source_type: str | None = None,
    topic: str | None = None,
    title: str | None = None,
    k: int = 5,
    emit: Callable[[dict], None] = lambda event: None,
    rewriter: Rewriter | None = None,
    reranker: Reranker | None = None,
    pool: int | None = None,
    score_ratio: float = 0.0,
) -> str:
    """Run the search and return text for the model. Never raises on bad arguments or empty results.
    `emit` receives the `citations` and `queries` events, and nothing when the search finds nothing.
    With a `rewriter` the search runs for the query and its rewrites, merged and de-duplicated to k chunks."""
    query = (query or "").strip()
    if not query:
        return "Error: query must not be empty."
    topic = (topic or "").strip().lower() or None
    title = (title or "").strip() or None
    filters = Filters(source_type=source_type, topics=(topic,) if topic else (), title=title)
    queries, chunks = retrieve_with_rewrites(retriever, rewriter, query, k, filters, reranker, pool, score_ratio)
    if not chunks:
        return NOT_FOUND
    emit({"type": "citations", "items": [citation_item(chunk) for chunk in chunks]})
    emit({"type": "queries", "items": queries})
    return "\n\n".join(format_chunk(chunk) for chunk in chunks)


def short_validation_error(error: ValidationError) -> str:
    problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
    return f"Error: invalid arguments ({problems}). Fix them or leave the filter out and retry."


def make_search_tool(
    retriever: Retriever,
    k: int = 5,
    rewriter: Rewriter | None = None,
    reranker: Reranker | None = None,
    pool: int | None = None,
    score_ratio: float = 0.0,
) -> StructuredTool:
    def run(query: str, source_type: str | None = None, topic: str | None = None, title: str | None = None) -> str:
        return search_knowledge_base(
            retriever, query, source_type, topic, title, k, stream_writer(), rewriter, reranker, pool, score_ratio
        )

    return StructuredTool.from_function(
        func=run,
        name="search_knowledge_base",
        description=DESCRIPTION,
        args_schema=SearchInput,
        handle_validation_error=short_validation_error,  # LangChain returns this instead of raising
    )
