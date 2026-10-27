from app.tools.delimit import parse_tool_result
from app.tools.frequency import make_note_frequency_tool, note_frequency


def test_450_hz_is_a4_plus_39_cents():
    result = note_frequency(frequency=450)
    assert result["nearest_note"] == "A4" and result["also_written"] == []
    assert result["cents"] == 38.9
    assert "C4 = middle C" in result["convention"]


def test_notes_to_frequencies():
    assert note_frequency("A4")["frequency_hz"] == 440.0
    assert note_frequency("C4")["frequency_hz"] == 261.63
    assert note_frequency("Bb3")["frequency_hz"] == 233.08
    assert note_frequency("Cb4")["frequency_hz"] == note_frequency("B3")["frequency_hz"]


def test_black_keys_give_both_spellings_and_flat_cents_are_negative():
    result = note_frequency(frequency=233.08)
    assert (result["nearest_note"], result["also_written"]) == ("A#3", ["Bb3"])
    assert note_frequency(frequency=430)["cents"] < 0
    assert note_frequency(frequency=261.63)["nearest_note"] == "C4"


def test_bad_input_is_a_structured_error():
    assert note_frequency("H4")["error"] == "invalid_note"
    assert note_frequency("A")["error"] == "invalid_note"
    for bad in (0, -440, float("nan"), float("inf")):
        assert note_frequency(frequency=bad)["error"] == "invalid_frequency"
    assert note_frequency()["error"] == "invalid_input"
    assert note_frequency("A4", 440)["error"] == "invalid_input"


def test_tool_rejects_non_numeric_frequency():
    tool = make_note_frequency_tool()
    assert parse_tool_result(tool.invoke({"frequency": "loud"}))["error"] == "invalid_input"
    assert parse_tool_result(tool.invoke({"frequency": 440}))["nearest_note"] == "A4"
