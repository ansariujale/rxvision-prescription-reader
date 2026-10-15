"""Tests for the Tesseract confidence calculation.

This exists because the production version of this filter was silently broken:
it compared each value against the *string* '-1' while pytesseract returns
ints, so the structural rows were never removed and the mean came out roughly
half what it should be. That pushed every page past the escalation threshold
and sent everything to Textract.
"""

from eval.ocr_runner import mean_confidence


def test_structural_rows_are_excluded():
    """The -1 rows are page/block/paragraph markers, not recognised words."""
    conf = [-1, -1, -1, 96, -1, 94, -1, 92]
    mean, count = mean_confidence(conf)
    assert count == 3
    assert mean == (96 + 94 + 92) / 3


def test_int_minus_one_is_actually_filtered():
    """The exact regression: ints must be compared as ints, not against '-1'."""
    conf = [-1] * 13 + [96] * 11
    mean, count = mean_confidence(conf)
    assert count == 11
    assert mean == 96.0
    # what the broken version produced on this input, for contrast
    broken = [int(c) for c in conf if c != "-1"]
    assert len(broken) == 24
    assert sum(broken) / len(broken) < 50


def test_string_inputs_still_work():
    """Older pytesseract versions hand back strings; both must behave the same."""
    assert mean_confidence(["-1", "80", "90"]) == mean_confidence([-1, 80, 90])


def test_all_structural_rows_gives_zero_not_a_crash():
    assert mean_confidence([-1, -1, -1]) == (0.0, 0)


def test_empty_input():
    assert mean_confidence([]) == (0.0, 0)


def test_a_clean_page_lands_above_the_default_threshold():
    """Regression guard on the actual consequence.

    A page Tesseract read well should sit above the default escalation
    threshold of 70, so it doesn't get needlessly sent to Textract. With the
    old filter this same input scored 43.
    """
    conf = [-1] * 13 + [96, 96, 96, 95, 96, 92, 96, 96, 96, 93, 96]
    mean, _ = mean_confidence(conf)
    assert mean > 70
