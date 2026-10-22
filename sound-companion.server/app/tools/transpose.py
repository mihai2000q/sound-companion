"""transpose_for_instrument: hand-written table (instruments.py), music21 only for the spelling."""
from typing import Annotated, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.tools.errors import tool_error
from app.tools.instruments import INSTRUMENTS, find_instrument
from app.tools.notes import CONVENTION, check_pitch_name, normalise_flats

DESCRIPTION = """Convert a note between the written pitch a player reads and the sounding pitch for a transposing \
instrument (for example a written C4 on a B-flat clarinet sounds Bb3). `direction` is 'written_to_sounding' (the \
default) or 'sounding_to_written'. Returns the resulting note, the interval used and the Citation for the \
instrument's transposition, which you must cite. An unknown instrument returns an error listing the known ones: \
ask the user which they mean, never guess. States the Convention it uses."""


class TransposeInput(BaseModel):
    note: Annotated[str, Field(description="Note with octave, for example 'C4'.")]
    instrument: Annotated[str, Field(description="Instrument, for example 'B-flat clarinet' or 'alto saxophone'.")]
    direction: Annotated[
        Literal["written_to_sounding", "sounding_to_written"],
        Field(description="Whether `note` is what the player reads or what is heard."),
    ] = "written_to_sounding"


def transpose_for_instrument(note: str, instrument: str, direction: str = "written_to_sounding") -> dict:
    """Written and sounding pitch for an instrument. Returns a structured error instead of raising."""
    from music21 import interval, pitch
    from music21.exceptions21 import Music21Exception

    row = find_instrument(instrument)
    if row is None:
        known = ", ".join(i.name for i in INSTRUMENTS)
        return tool_error("unknown_instrument", f"'{instrument}' is not in the transposition table. Known: {known}.")
    if direction not in ("written_to_sounding", "sounding_to_written"):
        return tool_error("invalid_input", "direction must be 'written_to_sounding' or 'sounding_to_written'.")
    name, error = check_pitch_name(note)
    if error:
        return error
    shift = interval.Interval(row.interval)
    if direction == "sounding_to_written":
        shift = shift.reverse()
    try:
        result = normalise_flats(pitch.Pitch(name).transpose(shift).nameWithOctave)
    except (Music21Exception, ValueError) as exc:
        return tool_error("invalid_input", str(exc))
    written, sounding = (name, result) if direction == "written_to_sounding" else (result, name)
    return {
        "instrument": row.name,
        "written_pitch": written,
        "sounding_pitch": sounding,
        "result": result,
        "direction": direction,
        "offset_semitones": shift.semitones,
        "citation": row.citation,
        "convention": CONVENTION,
    }


def make_transpose_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=transpose_for_instrument,
        name="transpose_for_instrument",
        description=DESCRIPTION,
        args_schema=TransposeInput,
        handle_validation_error=lambda e: tool_error(
            "invalid_input", "Give `note` (for example C4), `instrument` and optionally `direction`."
        ),
    )
