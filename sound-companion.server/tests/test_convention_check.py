import json
from pathlib import Path

from app.agent.convention_check import CASES, check_answer

Q06, Q12 = CASES

GOOD_Q06 = (
    "In scientific pitch notation middle C is C4 (Scientific pitch notation > Nomenclature), whereas Helmholtz "
    "notation calls it c′ (Musical note > Distinguishing pitches of different octaves). In German, B means "
    "B-flat and H means B natural (Musical note > Pitch names and their history)."
)


def test_complete_answer_passes():
    assert check_answer(Q06, GOOD_Q06).ok


def test_missing_convention_and_citation_are_named():
    result = check_answer(Q06, "Middle C is C4 (Scientific pitch notation > Nomenclature). The systems differ.")
    assert not result.ok
    assert result.missing_conventions == ["German B = B-flat", "German H = B natural"]
    assert result.missing_citations == ["German names page"]


def test_helmholtz_is_not_required_for_q06():
    answer = (
        "Middle C is C4 (Scientific pitch notation > Nomenclature). German names differ: B is B-flat and H is B natural "
        "(Musical note > Pitch names and their history)."
    )
    assert check_answer(Q06, answer).ok


def test_h_must_be_the_letter_not_part_of_a_word():
    answer = GOOD_Q06.replace("H means", "the letter means")
    assert check_answer(Q06, answer).missing_conventions == ["German H = B natural"]


def test_answer_without_a_statement_of_difference_fails():
    result = check_answer(Q06, GOOD_Q06.replace("whereas", "and").replace("different octaves", "octaves"))
    assert result.missing_conventions == [] and result.missing_citations == [] and not result.says_they_differ


def test_citation_by_url_slug_counts():
    answer = "Concert pitch is the sounded pitch, written pitch differs. https://en.wikipedia.org/wiki/Concert_pitch (Transposing instrument)"
    assert check_answer(Q12, answer).ok


def test_questions_match_the_golden_set():
    golden = json.loads((Path(__file__).resolve().parents[2] / "data" / "golden-set.json").read_text(encoding="utf-8"))
    by_id = {q["id"]: q["question"] for q in golden}
    assert all(case.question == by_id[case.id] for case in CASES)
