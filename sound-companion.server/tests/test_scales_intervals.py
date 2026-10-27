from app.tools.delimit import parse_tool_result
from app.tools.intervals import interval_between, make_interval_between_tool, make_scale_info_tool, scale_info


def test_c_major():
    result = scale_info("C", "major")
    assert result["notes"] == ["C", "D", "E", "F", "G", "A", "B"]
    assert result["key_signature"] == "no sharps or flats"
    assert "C4 = middle C" in result["convention"]


def test_flat_keys_are_spelled_with_b():
    result = scale_info("Eb", "major")
    assert result["notes"] == ["Eb", "F", "G", "Ab", "Bb", "C", "D"]
    assert result["key_signature"] == "3 flats"
    assert "-" not in str(result)


def test_modes_and_aliases():
    assert scale_info("D", "Dorian")["notes"] == ["D", "E", "F", "G", "A", "B", "C"]
    assert scale_info("A", "minor")["scale"] == "natural minor"
    assert scale_info("A", "minor")["key_signature"] == "no sharps or flats"
    assert scale_info("A", "melodic minor")["notes"][-2:] == ["F#", "G#"]
    assert scale_info("A", "dorian")["key_signature"] is None


def test_scale_errors_are_structured():
    assert scale_info("H", "major")["error"] == "invalid_note"
    assert scale_info("C", "bebop")["error"] == "unknown_scale"
    assert scale_info("C4", "major")["error"] == "invalid_note"


def test_perfect_fifth():
    result = interval_between("C4", "G4")
    assert (result["interval"], result["short_name"], result["semitones"], result["direction"]) == (
        "Perfect Fifth", "P5", 7, "up")
    assert "C4 = middle C" in result["convention"]


def test_compound_descending_and_flat_spelling():
    assert interval_between("C4", "G5")["semitones"] == 19
    assert interval_between("C4", "G5")["short_name"] == "P12"
    down = interval_between("G4", "C4")
    assert (down["semitones"], down["direction"]) == (-7, "down")
    assert interval_between("Bb3", "D5")["from"] == "Bb3"
    assert interval_between("C4", "C4")["direction"] == "same"


def test_interval_errors_are_structured():
    assert interval_between("H4", "C5")["error"] == "invalid_note"
    assert interval_between("C", "G4")["error"] == "invalid_note"  # the octave is required


def test_tools_survive_bad_arguments():
    assert parse_tool_result(make_scale_info_tool().invoke({"tonic": "C", "scale": "major"}))["notes"][0] == "C"
    assert parse_tool_result(make_interval_between_tool().invoke({"note_a": "C4"}))["error"] == "invalid_input"
