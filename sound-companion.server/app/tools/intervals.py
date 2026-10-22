"""scale_info and interval_between, built on music21 (imported lazily: it takes about 1.5 s to load)."""
from typing import Annotated

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.tools.errors import tool_error
from app.tools.notes import CONVENTION, check_note_names, check_pitch_name, normalise_flats

# Seven-note scales only: name -> (music21 class name, accepted aliases)
SCALES = {
    "major": ("MajorScale", ("ionian",)),
    "natural minor": ("MinorScale", ("minor", "aeolian")),
    "harmonic minor": ("HarmonicMinorScale", ()),
    "melodic minor": ("MelodicMinorScale", ()),
    "dorian": ("DorianScale", ()),
    "phrygian": ("PhrygianScale", ()),
    "lydian": ("LydianScale", ()),
    "mixolydian": ("MixolydianScale", ()),
    "locrian": ("LocrianScale", ()),
}
SCALE_ALIASES = {alias: name for name, (_, aliases) in SCALES.items() for alias in aliases}
KEY_MODES = {"major": "major", "natural minor": "minor"}

SCALE_DESCRIPTION = f"""List the notes of a scale from its tonic, with its key signature when it has one \
(major and natural minor). Supported scales: {', '.join(SCALES)} (also ionian, aeolian and minor). \
States the Convention it uses. Use it for any "what are the notes of ..." question instead of answering \
from memory. The tonic is a note name without octave (C, F#, Bb)."""

INTERVAL_DESCRIPTION = """Name the interval between two notes and give its size in semitones (negative when \
the second note is lower). Both notes need an octave (C4, Bb3), because C4 to G4 is a fifth and C4 to G5 is a \
twelfth. States the Convention it uses. Use it for any "what interval is ..." question instead of answering \
from memory."""


class ScaleInfoInput(BaseModel):
    tonic: Annotated[str, Field(description="Note name without octave, for example 'D' or 'Bb'.")]
    scale: Annotated[str, Field(description="Scale or mode, for example 'major', 'natural minor' or 'dorian'.")]


class IntervalInput(BaseModel):
    note_a: Annotated[str, Field(description="First note with octave, for example 'C4'.")]
    note_b: Annotated[str, Field(description="Second note with octave, for example 'G4'.")]


def key_signature(tonic: str, scale_name: str) -> str | None:
    from music21 import key

    sharps = key.Key(tonic, KEY_MODES[scale_name]).sharps
    if abs(sharps) > 7:  # keys such as C## major need double sharps, so no usable signature
        return None
    return "no sharps or flats" if sharps == 0 else f"{abs(sharps)} {'sharps' if sharps > 0 else 'flats'}"


def scale_info(tonic: str, scale: str) -> dict:
    """Notes of the scale. Returns a structured error instead of raising."""
    from music21 import scale as m21scale
    from music21.exceptions21 import Music21Exception

    names, error = check_note_names([tonic])
    if error:
        return error
    wanted = scale.strip().lower()
    wanted = SCALE_ALIASES.get(wanted, wanted)
    if wanted not in SCALES:
        return tool_error("unknown_scale", f"'{scale}' is not a supported scale. Choose one of: {', '.join(SCALES)}.")
    try:
        pitches = getattr(m21scale, SCALES[wanted][0])(names[0]).getPitches(f"{names[0]}4", f"{names[0]}5")
        signature = key_signature(names[0], wanted) if wanted in KEY_MODES else None
    except (Music21Exception, ValueError) as exc:
        return tool_error("invalid_input", str(exc))
    return {
        "tonic": names[0],
        "scale": wanted,
        "notes": [normalise_flats(p.name) for p in pitches[:-1]],  # the last pitch is the octave
        "key_signature": signature,
        "convention": CONVENTION,
    }


def interval_between(note_a: str, note_b: str) -> dict:
    """Interval from note_a to note_b. Returns a structured error instead of raising."""
    from music21 import interval, pitch
    from music21.exceptions21 import Music21Exception

    first, error = check_pitch_name(note_a)
    if error:
        return error
    second, error = check_pitch_name(note_b)
    if error:
        return error
    try:
        found = interval.Interval(pitch.Pitch(first), pitch.Pitch(second))
    except (Music21Exception, ValueError) as exc:
        return tool_error("invalid_input", str(exc))
    return {
        "from": first,
        "to": second,
        "interval": found.niceName,
        "short_name": found.name,
        "semitones": found.semitones,
        "direction": {1: "up", 0: "same", -1: "down"}[found.direction],
        "convention": CONVENTION,
    }


def _bad_arguments(_error) -> dict:
    return tool_error("invalid_input", "Check the arguments against the tool schema and try again.")


def make_scale_info_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=scale_info, name="scale_info", description=SCALE_DESCRIPTION, args_schema=ScaleInfoInput,
        handle_validation_error=_bad_arguments,
    )


def make_interval_between_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=interval_between, name="interval_between", description=INTERVAL_DESCRIPTION, args_schema=IntervalInput,
        handle_validation_error=_bad_arguments,
    )
