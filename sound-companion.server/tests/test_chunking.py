import re

from app.db.models import DocumentRecord
from app.rag.chunking import CHUNK_CHARS, OVERLAP_CHARS, chunk_document, split_text, title_line

SENTENCE = "The cor anglais is a transposing instrument pitched in F. "


def make_document(sections: list[dict], aliases: list[str] | None = None) -> DocumentRecord:
    return DocumentRecord(
        id=7,
        title="Cor anglais",
        source_type="encyclopedia",
        topics="|instruments|woodwinds|",
        aliases=["English horn"] if aliases is None else aliases,
        url="https://en.wikipedia.org/wiki/Cor_anglais",
        license="CC BY-SA 4.0",
        revision_id="123",
        sections=sections,
        char_count=sum(len(s["text"]) for s in sections),
    )


def test_short_text_is_one_piece():
    assert split_text("Short text.") == ["Short text."]


def test_pieces_stay_within_the_size():
    pieces = split_text(SENTENCE * 60)
    assert len(pieces) > 1
    assert all(len(piece) <= CHUNK_CHARS for piece in pieces)


def test_consecutive_pieces_overlap():
    pieces = split_text(" ".join(f"Sentence number {n} ends here." for n in range(80)))
    for before, after in zip(pieces, pieces[1:]):
        shared = next((n for n in range(len(after), 0, -1) if before.endswith(after[:n])), 0)
        assert OVERLAP_CHARS // 2 <= shared <= OVERLAP_CHARS  # about the overlap, moved to a word start


def test_words_are_not_cut():
    words = [f"word{n}" for n in range(500)]
    pieces = split_text(" ".join(words))
    for piece in pieces:
        assert set(piece.split()) <= set(words)


def test_text_without_spaces_still_terminates():
    pieces = split_text("x" * 2000)
    assert [len(p) for p in pieces][0] == CHUNK_CHARS
    assert "".join(pieces).count("x") >= 2000


def test_every_chunk_starts_with_the_title_and_alias_line():
    chunks = chunk_document(make_document([{"heading_path": [], "text": SENTENCE * 40}]))
    assert chunks
    assert all(c.content.startswith("Cor anglais (also: English horn)\n") for c in chunks)


def test_title_line_without_aliases_is_the_title():
    assert title_line("Piano", []) == "Piano"


def test_no_chunk_spans_two_sections_and_carries_its_heading_path():
    sections = [
        {"heading_path": ["Mode", "Dorian"], "text": "Dorian text. " * 100},
        {"heading_path": ["Mode", "Lydian"], "text": "Lydian text. " * 100},
        {"heading_path": [], "text": "Lead text."},
    ]
    chunks = chunk_document(make_document(sections))
    for chunk in chunks:
        body = chunk.content.split("\n", 1)[1]
        assert not ("Dorian" in body and "Lydian" in body)
        expected = {"Dorian": "Mode > Dorian", "Lydian": "Mode > Lydian", "Lead": ""}
        assert chunk.metadata["section"] == expected[re.search(r"Dorian|Lydian|Lead", body).group()]


def test_chunks_carry_the_document_metadata():
    chunk = chunk_document(make_document([{"heading_path": ["History"], "text": "Text."}]))[0]
    assert chunk.metadata == {
        "document_id": "7", "title": "Cor anglais", "aliases": "English horn",
        "source_type": "encyclopedia", "topics": "|instruments|woodwinds|", "section": "History",
        "url": "https://en.wikipedia.org/wiki/Cor_anglais", "license": "CC BY-SA 4.0",
        "revision_id": "123",
    }


def test_ids_are_stable_and_unique():
    sections = [{"heading_path": ["A"], "text": SENTENCE * 40}, {"heading_path": ["B"], "text": SENTENCE * 40}]
    first = [c.id for c in chunk_document(make_document(sections))]
    second = [c.id for c in chunk_document(make_document(sections))]
    assert first == second
    assert len(set(first)) == len(first)


def test_empty_sections_make_no_chunks():
    assert chunk_document(make_document([{"heading_path": ["Empty"], "text": "  \n "}])) == []
