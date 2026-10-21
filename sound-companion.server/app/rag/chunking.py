import uuid
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.db.models import DocumentRecord

CHUNK_CHARS = 800
OVERLAP_CHARS = 100

# Fixed namespace, so the same document, section and chunk index always give the same id.
CHUNK_NAMESPACE = uuid.UUID("5f0d6d3a-3c1e-4f0a-9d56-6a1b0c1f7a20")

# The metadata columns of the chunk table (docs/DATABASE-SCHEMA.md), the one list the table setup
# and the vector store both use.
METADATA_COLUMNS = [
    "document_id", "title", "aliases", "source_type", "topics", "section", "url", "license",
    "revision_id",
]

_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_CHARS, chunk_overlap=OVERLAP_CHARS)


@dataclass
class Chunk:
    id: uuid.UUID
    content: str  # the title and Alias line, then the text
    metadata: dict[str, str]


def title_line(title: str, aliases: list[str]) -> str:
    """`Cor anglais (also: English horn)`, or just the title when there are no Aliases."""
    return f"{title} (also: {', '.join(aliases)})" if aliases else title


def split_text(text: str) -> list[str]:
    """Windows of about `CHUNK_CHARS` characters with `OVERLAP_CHARS` of overlap, broken at a
    paragraph, line, space or character, in that order."""
    return _splitter.split_text(text)


def chunk_id(url: str, section_index: int, chunk_index: int) -> uuid.UUID:
    return uuid.uuid5(CHUNK_NAMESPACE, f"{url}|{section_index}|{chunk_index}")


def chunk_document(document: DocumentRecord) -> list[Chunk]:
    """Split a stored document into chunks. No chunk crosses a section boundary."""
    header = title_line(document.title, document.aliases)
    chunks: list[Chunk] = []
    for section_index, section in enumerate(document.sections):
        path = " > ".join(section["heading_path"])
        for chunk_index, piece in enumerate(split_text(section["text"])):
            metadata = {
                "document_id": str(document.id),
                "title": document.title,
                "aliases": "|".join(document.aliases),
                "source_type": document.source_type,
                "topics": document.topics,
                "section": path,
                "url": document.url,
                "license": document.license,
                "revision_id": document.revision_id,
            }
            chunks.append(
                Chunk(chunk_id(document.url, section_index, chunk_index), f"{header}\n{piece}", metadata)
            )
    return chunks
