from app.tools.chords import chord_info, make_chord_info_tool
from app.tools.notes import check_note_names, normalise_flats


def test_ambiguous_notes_return_every_candidate():
    result = chord_info(["D", "F", "A", "C"])
    assert [c["symbol"] for c in result["candidates"]] == ["Dm7", "F6/D"]
    assert result["candidates"][1]["root"] == "F" and result["candidates"][1]["bass"] == "D"
    assert "C4 = middle C" in result["convention"]


def test_flats_and_sharps():
    assert chord_info(["Bb", "D", "F"])["candidates"][0]["symbol"] == "Bb"
    assert chord_info(["B-", "D", "F"])["candidates"][0]["symbol"] == "Bb"  # music21 spelling is accepted
    assert chord_info(["C#", "E", "G#"])["candidates"][0]["symbol"] == "C#m"


def test_invalid_note_is_a_structured_error_not_an_exception():
    result = chord_info(["H", "D", "F"])
    assert result["error"] == "invalid_note"
    assert "German" in result["message"]


def test_octaves_and_lowercase_are_rejected():
    assert chord_info(["C4", "E4", "G4"])["error"] == "invalid_note"
    assert chord_info(["c", "e", "g"])["error"] == "invalid_note"


def test_no_matching_chord():
    assert chord_info(["C", "C#", "D"])["error"] == "no_chord"


def test_tool_survives_bad_arguments():
    tool = make_chord_info_tool()
    assert tool.invoke({"notes": ["C"]})["error"] == "invalid_input"


def test_helpers():
    assert normalise_flats("E-") == "Eb"
    assert check_note_names(["Xyz"])[1]["error"] == "invalid_note"
