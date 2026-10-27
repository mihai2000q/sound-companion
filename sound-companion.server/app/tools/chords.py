from typing import Annotated

from langchain_core.tools import StructuredTool
from pychord import find_chords_from_notes
from pydantic import BaseModel, Field

from app.tools.errors import tool_error
from app.tools.delimit import delimited
from app.tools.notes import CONVENTION, check_note_names

DESCRIPTION = """Name the chord formed by some notes. Returns every Candidate (an ambiguous set of notes has \
several, for example D F A C is Dm7 and F6/D) with its chord symbol, root, quality and bass note, and states \
the Convention it uses. Use it for any "what chord is this" question instead of answering from memory. \
Give note names without octaves; an invalid note returns an error to explain to the user."""


class ChordInfoInput(BaseModel):
    notes: Annotated[
        list[str],
        Field(description="Note names without octaves, for example ['D', 'F', 'A', 'C'] or ['Bb', 'D', 'F'].", min_length=2),
    ]


def chord_info(notes: list[str]) -> dict:
    """Every Candidate chord for the notes. Returns a structured error instead of raising."""
    clean, error = check_note_names(notes)
    if error:
        return error
    try:
        found = find_chords_from_notes(clean)
    except ValueError as exc:  # pychord raises ValueError for unknown notes and too few notes
        return tool_error("invalid_input", str(exc))
    if not found:
        return tool_error("no_chord", f"No chord matches the notes {', '.join(clean)}.")
    return {
        "notes": clean,
        "candidates": [
            {"symbol": c.chord, "root": c.root, "quality": c.quality.quality, "bass": c.on or c.root, "notes": c.components()}
            for c in found
        ],
        "convention": CONVENTION,
    }


def make_chord_info_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=delimited("chord_info", chord_info),
        name="chord_info",
        description=DESCRIPTION,
        args_schema=ChordInfoInput,
        handle_validation_error=lambda e: tool_error("invalid_input", "notes must be a list of at least two note names."),
    )
