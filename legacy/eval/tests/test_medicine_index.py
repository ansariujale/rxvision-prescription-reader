"""Tests for the trigram medicine index.

Two of these guard mistakes that were made and measured during development:

  - stripping dosage forms as substrings destroys real drug names
    ("ventab dxt" -> "ven dxt"), so it has to be token-level
  - stripping with a plain regex works on the clean dataset but not on OCR
    output ("tablel"), which leaves the query carrying a token the dataset
    entry no longer has and makes matching *worse* than not stripping at all
"""

import pytest
from rapidfuzz import fuzz, process

from medicine_index import (
    MedicineIndex,
    normalize,
    strip_dosage_form,
    trigrams,
)

DRUGS = [
    "Augmentin 625 Duo Tablet",
    "Augmentin 1000 Duo Tablet",
    "Azithral 500 Tablet",
    "Azithral 500 Injection",
    "Pantop 40 Tablet",
    "Dolo 650 Tablet",
    "Clopilet 75 Tablet",
    "Ventab DXT Tablet",
    "Janumet 50/500 Tablet",
    "Ascoril LS Syrup",
    "Amoxicillin 500 Capsule",
    "Betnovate C Cream",
]


@pytest.fixture(scope="module")
def index():
    return MedicineIndex(DRUGS)


# -- stripping ------------------------------------------------------------

@pytest.mark.parametrize(
    "name",
    ["clopilet", "ventab dxt", "janumet", "betnovate", "tablature", "captopril"],
)
def test_drug_names_containing_form_words_survive(name):
    """The substring-vs-token distinction. Getting this wrong destroys names."""
    assert strip_dosage_form(name) == name


@pytest.mark.parametrize(
    "text,expected",
    [
        ("augmentin 625 duo tablet", "augmentin 625 duo"),
        ("azithral 500 injection", "azithral 500"),
        ("ascoril ls syrup", "ascoril ls"),
        ("amoxicillin 500 capsule", "amoxicillin 500"),
        ("betnovate c cream", "betnovate c"),
        ("pantop 40 tab", "pantop 40"),
    ],
)
def test_clean_form_words_are_removed(text, expected):
    assert strip_dosage_form(text) == expected


@pytest.mark.parametrize(
    "damaged,expected",
    [
        ("dolo 650 tablel", "dolo 650"),
        ("augmentin 625 duo tablel", "augmentin 625 duo"),
        ("ascoril ls syrvp", "ascoril ls"),
        ("azithral 500 injectiori", "azithral 500"),
        ("pantop 40 tablrt", "pantop 40"),
    ],
)
def test_ocr_damaged_form_words_are_also_removed(damaged, expected):
    """The asymmetry bug: strip the dataset but not the query and matching gets worse."""
    assert strip_dosage_form(damaged) == expected


def test_stripping_everything_leaves_nothing():
    assert strip_dosage_form("tablet") == ""


# -- trigrams -------------------------------------------------------------

def test_trigrams_are_padded_so_short_names_still_index():
    assert trigrams("dolo") == {"  d", " do", "dol", "olo", "lo "}


def test_one_wrong_character_leaves_most_trigrams_intact():
    """Why trigrams and not hashing: OCR damage is local."""
    good, bad = trigrams("augmentin"), trigrams("augrnentin")
    shared = good & bad
    assert len(shared) >= len(good) * 0.5, f"only {len(shared)} of {len(good)} survived"


# -- matching -------------------------------------------------------------

def test_exact_name_matches(index):
    hit = index.match("Augmentin 625 Duo Tablet")
    assert hit is not None
    assert hit[0] == "augmentin 625 duo"
    assert hit[1] == 100.0


def test_ocr_corrupted_name_still_matches(index):
    hit = index.match("Augrnentin 625 Duo Tablel")
    assert hit is not None
    assert hit[0] == "augmentin 625 duo"


def test_non_medicine_lines_are_rejected(index):
    for line in ["dr r k sharma mbbs md", "take twice daily after food", "review after 5 days"]:
        assert index.match(line) is None, f"{line!r} should not match a drug"


def test_empty_and_whitespace_lines(index):
    assert index.match("") is None
    assert index.match("   ") is None
    assert index.match("tablet") is None


def test_threshold_is_respected(index):
    """A badly damaged name matches at a low bar and not at a high one."""
    damaged = "augrn3ntin 625 du0"
    assert index.match(damaged, threshold=50) is not None
    assert index.match(damaged, threshold=99) is None


def test_match_all_finds_every_medicine_in_a_block(index):
    text = (
        "Dr R K Sharma MBBS MD\n"
        "Augmentin 625 Duo Tablet\n"
        "take twice daily\n"
        "Pantop 40 Tablet\n"
        "review after 5 days"
    )
    found = index.match_all(text)
    assert "augmentin 625 duo" in found
    assert "pantop 40" in found


def test_original_name_recoverable_after_stripping(index):
    """Stripping merges products, so the full name has to stay reachable."""
    hit = index.match("Azithral 500 Tablet")
    assert hit is not None
    assert index.original[hit[2]].lower().startswith("azithral 500")


# -- the filter must not change the answer --------------------------------

@pytest.mark.parametrize(
    "line",
    [
        "Augmentin 625 Duo Tablet",
        "Augrnentin 625 Duo Tablel",
        "pantop 40",
        "dolo 650 tablet",
        "clopilet 75",
        "ventab dxt",
        "janumet 50/500",
        "dr r k sharma mbbs md",
        "xyzzy plugh frobnicate",
    ],
)
def test_index_agrees_with_brute_force(index, line):
    """The index narrows candidates; it must not change the verdict.

    Brute force here scores against every key rather than the top-k subset.
    """
    query = strip_dosage_form(normalize(line))
    brute = (
        process.extractOne(query, index.keys, scorer=fuzz.token_sort_ratio, score_cutoff=68)
        if query
        else None
    )
    indexed = index.match(line)

    assert (brute is None) == (indexed is None), f"disagreement on {line!r}"
    if brute is not None:
        assert abs(brute[1] - indexed[1]) < 0.01


def test_candidates_narrow_the_field(index):
    """The whole point: score fewer names than the dataset holds."""
    cands = index.candidates(strip_dosage_form(normalize("augrnentin 625 duo")))
    assert 0 < len(cands) <= len(index.keys)


def test_unrelated_query_returns_few_or_no_candidates(index):
    assert index.match("zzzzz qqqqq wwwww") is None


# -- persistence ----------------------------------------------------------

def test_save_and_load_round_trip(index, tmp_path):
    path = tmp_path / "idx.pkl"
    index.save(path)
    loaded = MedicineIndex.load(path)

    assert loaded.keys == index.keys
    assert loaded.original == index.original
    assert loaded.top_k == index.top_k
    assert loaded.match("Augrnentin 625 Duo Tablel") == index.match("Augrnentin 625 Duo Tablel")


def test_small_datasets_keep_every_trigram():
    """A percentage cut alone is meaningless when the dataset is tiny.

    At 12 names a 10% cut is 1.2, so any trigram shared by two names would be
    dropped - which made 'azithral 500' unfindable because it appears as both
    a tablet and an injection. The absolute floor prevents that.
    """
    index = MedicineIndex(DRUGS, stop_cut=0.10)
    unfiltered = MedicineIndex(DRUGS, stop_cut=1.0)
    assert index.posting_count == unfiltered.posting_count

    duplicated = index.match("Azithral 500 Tablet")
    assert duplicated is not None, "a name appearing twice must still be findable"


def test_stop_cut_drops_ubiquitous_trigrams_on_a_large_dataset():
    """Above the floor, the percentage cut does take effect."""
    many = [f"drugname{i} tablet" for i in range(2000)]
    permissive = MedicineIndex(many, stop_cut=1.0)
    aggressive = MedicineIndex(many, stop_cut=0.02)
    assert aggressive.posting_count < permissive.posting_count
