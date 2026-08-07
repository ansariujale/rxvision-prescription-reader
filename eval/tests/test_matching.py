"""Tests for the evaluation matcher.

The important one is test_agrees_with_production: eval/matching.py is a
hoisted copy of text_extraction.match_medicine, and the whole harness is only
trustworthy if the two produce identical output.
"""

import time

import pytest

from eval.matching import match_medicines, normalize_text

DATASET = [
    "Augmentin 625 Duo Tablet",
    "Azithral 500 Tablet",
    "Pantop 40 Tablet",
    "Crocin Advance Tablet",
    "Dolo 650 Tablet",
]


def production_match(extracted_text, medicine_names, threshold=68):
    """text_extraction.match_medicine, copied verbatim minus the import.

    Kept here rather than imported because importing text_extraction builds a
    boto3 client, and these tests should run with no AWS setup at all.
    """
    from rapidfuzz import fuzz, process

    results = []
    for text in extracted_text.split("\n"):
        text = normalize_text(text.strip())
        normalized_dataset = [normalize_text(name) for name in medicine_names]
        match = process.extractOne(text, normalized_dataset, scorer=fuzz.token_sort_ratio)
        if match and match[1] >= threshold:
            results.append(match[0])
    return results


@pytest.mark.parametrize(
    "text",
    [
        "Augmentin 625 Duo Tablet",
        "augmentin 625 duo tablet\npantop 40 tablet",
        "Augrnentin 625 Duo Tablel\nPant0p 40 Tablet",   # OCR-style corruption
        "",
        "\n\n\n",
        "complete gibberish xyzzy",
        "Dolo 650mg\nCrocin Advance",
    ],
)
@pytest.mark.parametrize("threshold", [50, 68, 90])
def test_agrees_with_production(text, threshold):
    assert match_medicines(text, DATASET, threshold) == production_match(text, DATASET, threshold)


def test_returns_normalised_dataset_entries():
    got = match_medicines("Augmentin 625 Duo Tablet", DATASET)
    assert got == ["augmentin 625 duo tablet"]


def test_ocr_corruption_still_matches():
    """The point of fuzzy matching: a couple of wrong characters shouldn't lose the drug."""
    assert match_medicines("Augrnentin 625 Duo Tablel", DATASET, threshold=68) == [
        "augmentin 625 duo tablet"
    ]


def test_high_threshold_rejects_a_bad_read():
    assert match_medicines("Augrnentin 625 Duo Tablel", DATASET, threshold=99) == []


def test_gibberish_does_not_match():
    assert match_medicines("xyzzy plugh frobnicate", DATASET, threshold=68) == []


def test_hoisting_is_actually_faster():
    """Guards the reason this module exists.

    Production re-normalises the whole dataset per line. With a dataset of any
    real size that dominates; this asserts the hoisted version wins clearly on
    a multi-line input.
    """
    dataset = DATASET * 400          # ~2,000 names
    text = "\n".join(["Augmentin 625 Duo Tablet"] * 8)

    start = time.perf_counter()
    fast = match_medicines(text, dataset)
    fast_seconds = time.perf_counter() - start

    start = time.perf_counter()
    slow = production_match(text, dataset)
    slow_seconds = time.perf_counter() - start

    assert fast == slow, "the optimisation changed the answer"
    assert fast_seconds < slow_seconds, (
        f"expected the hoisted version to win: {fast_seconds:.4f}s vs {slow_seconds:.4f}s"
    )
