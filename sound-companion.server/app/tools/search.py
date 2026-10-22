from typing import Annotated, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, ValidationError

from app.rag.retriever import Filters, RetrievedChunk, Retriever

NOT_FOUND = (
    "Nothing relevant found in the knowledge base for this query. "
    "Say so to the user and do not answer from memory."
)

DESCRIPTION = """Search the music knowledge base (Wikipedia articles and the Open Music Theory textbook) \
for explanations and facts about music theory and instruments. Returns text chunks, each with its page \
title, section, URL, licence and a similarity score. Cite the page and section of every fact you use.

Use it for: what a concept is, how an instrument works, history, terminology, and which pages exist on \
a subject (for example to list the kinds of guitar before asking the user which one they mean).
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
    return (
        f"[{location}] url: {chunk.url} | license: {chunk.license} | score: {chunk.score:.3f}\n{chunk.content}"
    )


def search_knowledge_base(
    retriever: Retriever,
    query: str,
    source_type: str | None = None,
    topic: str | None = None,
    title: str | None = None,
    k: int = 5,
) -> str:
    """Run the search and return text for the model. Never raises on bad arguments or empty results."""
    query = (query or "").strip()
    if not query:
        return "Error: query must not be empty."
    topic = (topic or "").strip().lower() or None
    title = (title or "").strip() or None
    filters = Filters(source_type=source_type, topics=(topic,) if topic else (), title=title)
    chunks = retriever.retrieve(query, k, filters)
    if not chunks:
        return NOT_FOUND
    return "\n\n".join(format_chunk(chunk) for chunk in chunks)


def short_validation_error(error: ValidationError) -> str:
    problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
    return f"Error: invalid arguments ({problems}). Fix them or leave the filter out and retry."


def make_search_tool(retriever: Retriever, k: int = 5) -> StructuredTool:
    def run(query: str, source_type: str | None = None, topic: str | None = None, title: str | None = None) -> str:
        return search_knowledge_base(retriever, query, source_type, topic, title, k)

    return StructuredTool.from_function(
        func=run,
        name="search_knowledge_base",
        description=DESCRIPTION,
        args_schema=SearchInput,
        handle_validation_error=short_validation_error,  # LangChain returns this instead of raising
    )
