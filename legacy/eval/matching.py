"""Medicine-name matching for the evaluation harness.

This is a faster copy of `match_medicine` from text_extraction.py. The
production version re-normalises the entire medicine dataset inside its
per-line loop:

    for text in extracted_text.split("\\n"):
        normalized_dataset = [normalize_text(name) for name in medicine_names]

With ~254,000 names and a ten-line prescription that is around 2.5 million
redundant string operations per image, which makes a threshold sweep across
hundreds of images unusable.

Hoisting a loop-invariant out of a loop cannot change the result, and
tests/test_matching.py asserts that this and the production function agree on
the same inputs. If that test ever fails, this file is wrong, not the test.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from rapidfuzz import fuzz, process


def normalize_text(text: str) -> str:
    """Same rule as text_extraction.normalize_text."""
    return text.lower().replace("mg", "").strip()


@lru_cache(maxsize=4)
def _normalized(dataset: tuple[str, ...]) -> tuple[str, ...]:
    """Normalise the dataset once and reuse it across every line and image."""
    return tuple(normalize_text(name) for name in dataset)


def match_medicines(
    extracted_text: str,
    medicine_names: Sequence[str],
    threshold: int = 68,
) -> list[str]:
    """Fuzzy-match each line of OCR output against the medicine dataset.

    Returns the matched dataset entries, normalised - which is what the
    production pipeline returns too.
    """
    dataset = _normalized(tuple(medicine_names))

    results: list[str] = []
    for line in extracted_text.split("\n"):
        # Deliberately not skipping blank lines: production doesn't either, and
        # this needs to stay a pure hoist so the equivalence test means something.
        line = normalize_text(line.strip())
        match = process.extractOne(line, dataset, scorer=fuzz.token_sort_ratio)
        if match and match[1] >= threshold:
            results.append(match[0])
    return results


def load_medicine_names(csv_path: str) -> list[str]:
    """Read the `name` column out of the medicine dataset."""
    import pandas as pd

    df = pd.read_csv(csv_path)
    return [str(n).lower().strip() for n in df["name"].tolist()]
