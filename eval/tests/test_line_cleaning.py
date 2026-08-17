"""Tests for stripping prescription line noise.

Real prescriptions don't hand you a bare drug name. They hand you "1. scata 25"
or "t. catel 40". That prefix counts toward the similarity score and pushes
correctly-read drugs under the threshold - measured on 30 labelled
prescriptions, 22 of 85 medicines were legible in the OCR text but missed.
"""

import pytest

from medicine_index import MIN_LINE_LENGTH, MedicineIndex, clean_ocr_line

DRUGS = [
    "Augmentin 625 Duo Tablet",
    "Pantop 40 Tablet",
    "Catel 40 Tablet",
    "Divaa OD 500 Tablet",
    "Clopilet 75 Tablet",
]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1. scata 25", "scata 25"),          # numbered list
        ("2) pantop 40", "pantop 40"),
        ("3 - divaa od 500", "divaa od 500"),
        ("t. catel 40", "catel 40"),          # T. for Tablet
        ("c. amoxicillin", "amoxicillin"),
        ("s- augmentin 625", "augmentin 625"),
        ("tab. pantop 40", "pantop 40"),      # spelled-out abbreviation
        ("inj. rantac", "rantac"),
        ("(pantop 40", "pantop 40"),          # stray bracket
        ("- - dolo 650", "dolo 650"),
        ("1. t. catel 40", "catel 40"),       # both, stacked
    ],
)
def test_leading_noise_is_stripped(raw, expected):
    assert clean_ocr_line(raw) == expected


@pytest.mark.parametrize(
    "line",
    [
        "augmentin 625 duo",
        "clopilet 75",
        "divaa od 500",
        "pantop 40",
    ],
)
def test_clean_lines_are_left_alone(line):
    assert clean_ocr_line(line) == line


def test_drug_names_are_not_eaten():
    """The regex must not chew into the name itself.

    'tab' as a whole leading word goes, but a name that merely starts with
    those letters has to survive - the same substring-vs-token distinction as
    the dosage-form stripper.
    """
    assert clean_ocr_line("ventab dxt") == "ventab dxt"
    assert clean_ocr_line("tabsule x") == "tabsule x"
    assert clean_ocr_line("capsicum plus") == "capsicum plus"


def test_a_bare_dosage_word_is_stripped_even_without_punctuation():
    """"Caps 500" is a dosage form and a strength, not a drug name.

    The separator is optional in the pattern, so a leading "caps" goes whether
    or not it was written "caps." - what's left is too short to match anything
    and gets dropped by the length filter, which is the right outcome.
    """
    assert clean_ocr_line("caps 500") == "500"
    assert clean_ocr_line("tab 40") == "40"


def test_noise_in_the_middle_is_left():
    """Only the leading run is stripped. Mid-line junk is a different problem."""
    assert clean_ocr_line("pantop 40 (1-0-1)") == "pantop 40 (1-0-1)"


def test_a_line_that_is_only_noise_becomes_empty():
    assert clean_ocr_line("1.") == ""
    assert clean_ocr_line("---") == ""


# -- how it changes matching ---------------------------------------------

@pytest.fixture(scope="module")
def index():
    return MedicineIndex(DRUGS)


def test_cleaning_raises_the_score_on_a_numbered_line(index):
    """The case this was built for.

    Against five drugs the prefix doesn't stop the match - there's nothing else
    to confuse it with. Against 254,000 names it's the difference between
    clearing the threshold and not, so what this asserts is the direction:
    stripping the prefix always scores at least as well, and here better.
    """
    dirty = index.match("3. divaa od 500", clean=False, min_length=0)
    clean = index.match("3. divaa od 500")

    assert clean is not None
    assert clean[0] == "divaa od 500"
    assert clean[1] > dirty[1], f"cleaning should improve the score: {clean[1]} vs {dirty[1]}"
    assert clean[1] == 100.0, "with the prefix gone it should be an exact match"


def test_short_junk_no_longer_matches(index):
    """69 of 233 returns were three characters or shorter before this."""
    for junk in ["x", "10", "r", "af"]:
        assert index.match(junk) is None, f"{junk!r} should not match a medicine"


def test_min_length_is_enforced(index):
    assert len("pan 4") < MIN_LINE_LENGTH
    assert index.match("pan 4") is None
    assert index.match("pan 4", min_length=0) is not None


def test_cleaning_can_be_switched_off(index):
    """Both switches exist so the effect stays measurable rather than assumed."""
    assert index.match("1. pantop 40", clean=True) is not None
    assert index.match("1. pantop 40", clean=False, min_length=0)[1] < 100
