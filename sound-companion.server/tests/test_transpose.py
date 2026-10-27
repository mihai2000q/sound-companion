import pytest
from music21 import interval, pitch

from app.tools.delimit import parse_tool_result
from app.tools.instruments import INSTRUMENTS, find_instrument
from app.tools.transpose import make_transpose_tool, transpose_for_instrument


def test_written_c4_on_a_bb_clarinet_sounds_bb3():
    result = transpose_for_instrument("C4", "B-flat clarinet")
    assert (result["written_pitch"], result["sounding_pitch"], result["offset_semitones"]) == ("C4", "Bb3", -2)
    assert result["citation"]["title"] == "List of transposing instruments"
    assert result["citation"]["url"].startswith("https://en.wikipedia.org/")
    assert result["citation"]["license"] == "CC BY-SA 4.0"
    assert "C4 = middle C" in result["convention"]


def test_sounding_to_written_reverses():
    result = transpose_for_instrument("Bb3", "B-flat clarinet", "sounding_to_written")
    assert (result["written_pitch"], result["sounding_pitch"]) == ("C4", "Bb3")


@pytest.mark.parametrize("row", INSTRUMENTS, ids=lambda r: r.key)
def test_every_row_matches_its_sourced_c4(row):
    """The interval is derived from the page's cell, so both must agree."""
    assert pitch.Pitch("C4").transpose(interval.Interval(row.interval)).nameWithOctave.replace("-", "b") == row.sounding_c4
    assert row.citation["url"] and row.citation["license"]
    assert transpose_for_instrument("C4", row.name)["citation"] == row.citation


def test_spelling_and_octaves():
    assert transpose_for_instrument("C4", "alto saxophone")["result"] == "Eb3"
    assert transpose_for_instrument("C4", "baritone saxophone")["result"] == "Eb2"
    assert transpose_for_instrument("C4", "guitar")["result"] == "C3"
    assert transpose_for_instrument("C4", "piccolo")["result"] == "C5"
    assert transpose_for_instrument("C4", "A clarinet")["result"] == "A3"


def test_names_are_forgiving():
    for text in ("Bb clarinet", "clarinet in B♭", "b-flat clarinet", " B-FLAT  Clarinet "):
        assert find_instrument(text).key == "bb_clarinet"
    assert find_instrument("English horn").key == find_instrument("cor anglais").key


def test_unknown_instrument_lists_the_known_ones():
    for name in ("kazoo", "clarinet"):  # "clarinet" alone is ambiguous: no guess
        result = transpose_for_instrument("C4", name)
        assert result["error"] == "unknown_instrument"
        assert "B-flat clarinet" in result["message"]


def test_bad_note_and_direction():
    assert transpose_for_instrument("H4", "guitar")["error"] == "invalid_note"
    assert transpose_for_instrument("C", "guitar")["error"] == "invalid_note"
    assert transpose_for_instrument("C4", "guitar", "sideways")["error"] == "invalid_input"


def test_tool_wrapper():
    tool = make_transpose_tool()
    assert parse_tool_result(tool.invoke({"note": "C4", "instrument": "alto sax"}))["result"] == "Eb3"
    assert parse_tool_result(tool.invoke({"note": "C4"}))["error"] == "invalid_input"
