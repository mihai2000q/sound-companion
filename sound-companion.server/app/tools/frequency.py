"""note_frequency: hand-written, A4 = 440 Hz in equal temperament. A note gives its frequency, and a frequency
gives the nearest note plus the offset in cents."""
import math
from typing import Annotated

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.tools.errors import tool_error
from app.tools.delimit import delimited
from app.tools.notes import CONVENTION, check_pitch_name

A4_HZ = 440.0
A4_MIDI = 69
LETTER_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

DESCRIPTION = f"""Convert between a note and its frequency (A4 = {A4_HZ:.0f} Hz, equal temperament). Give `note` \
with an octave (A4, Bb3) to get its frequency in Hz, or give `frequency` in Hz to get the nearest note and how \
many cents sharp (+) or flat (-) the frequency is from it. Give exactly one of the two. States the Convention \
it uses. Use it for any frequency or pitch-detection question instead of calculating in your head."""


class NoteFrequencyInput(BaseModel):
    note: Annotated[str | None, Field(description="Note with octave, for example 'A4' or 'Bb3'.")] = None
    frequency: Annotated[float | None, Field(description="Frequency in Hz, for example 450.")] = None


def note_to_midi(name: str) -> int:
    """MIDI number of a validated pitch name such as C4 or Bb3 (C4 = 60)."""
    letter, accidentals, octave = name[0], name[1:-1], int(name[-1])
    shift = accidentals.count("#") - accidentals.count("b")
    return 12 * (octave + 1) + LETTER_SEMITONES[letter] + shift


def midi_to_frequency(midi: float) -> float:
    return A4_HZ * 2 ** ((midi - A4_MIDI) / 12)


def note_frequency(note: str | None = None, frequency: float | None = None) -> dict:
    """Note to Hz, or Hz to the nearest note and cents. Returns a structured error instead of raising."""
    if (note is None) == (frequency is None):
        return tool_error("invalid_input", "Give exactly one of `note` (for example A4) or `frequency` (in Hz).")
    if note is not None:
        name, error = check_pitch_name(note)
        if error:
            return error
        return {"note": name, "frequency_hz": round(midi_to_frequency(note_to_midi(name)), 2), "convention": CONVENTION}
    if not math.isfinite(frequency) or frequency <= 0:
        return tool_error("invalid_frequency", f"{frequency} is not a usable frequency. It must be a number above 0 Hz.")
    exact = A4_MIDI + 12 * math.log2(frequency / A4_HZ)
    nearest = round(exact)
    octave, index = divmod(nearest, 12)
    names = [f"{SHARP_NAMES[index]}{octave - 1}"]
    if FLAT_NAMES[index] != SHARP_NAMES[index]:
        names.append(f"{FLAT_NAMES[index]}{octave - 1}")
    return {
        "frequency_hz": frequency,
        "nearest_note": names[0],
        "also_written": names[1:],  # the flat spelling of a black key
        "nearest_note_hz": round(midi_to_frequency(nearest), 2),
        "cents": round((exact - nearest) * 100, 1),
        "convention": CONVENTION,
    }


def make_note_frequency_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=delimited("note_frequency", note_frequency),
        name="note_frequency",
        description=DESCRIPTION,
        args_schema=NoteFrequencyInput,
        handle_validation_error=lambda e: tool_error(
            "invalid_input", "`note` must be text like A4 and `frequency` a number in Hz."
        ),
    )
