"""Note-name helpers shared by the music tools."""
import re

from app.tools.errors import GERMAN_H_HINT, tool_error

CONVENTION = "Scientific pitch notation, C4 = middle C. Flats are written with b and sharps with #."

NOTE_NAME = re.compile(r"[A-G](?:#{1,2}|b{1,2})?")


def normalise_flats(text: str) -> str:
    """music21 spells flats with `-` (B-, E-); we write b."""
    return text.replace("-", "b")


def check_note_names(notes: list[str]) -> tuple[list[str], dict | None]:
    """Return (clean note names, None), or ([], a structured error) for the first invalid name."""
    clean = []
    for raw in notes:
        name = normalise_flats(raw.strip())
        if not NOTE_NAME.fullmatch(name):
            hint = f" {GERMAN_H_HINT}" if name[:1] in ("H", "h") else ""
            return [], tool_error(
                "invalid_note",
                f"'{raw}' is not a note name. Use a letter A to G, optionally followed by # or b, "
                f"without an octave (for example C, F#, Bb).{hint}",
            )
        clean.append(name)
    return clean, None
