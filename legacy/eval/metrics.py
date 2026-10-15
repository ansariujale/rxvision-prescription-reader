"""Scoring for prescription extraction.

The pipeline returns a set of medicine names per prescription, so this compares
sets rather than strings. There is no ordering to get right and duplicates
don't mean anything, which keeps the scoring simple.

Nothing in here touches OCR, images, or the network, so it is all unit
testable and runs in milliseconds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


def normalize(name: str) -> str:
    """Mirror of `normalize_text` in text_extraction.py.

    Ground truth has to be normalised the same way the pipeline normalises its
    own output, or we end up measuring formatting differences instead of OCR
    quality.
    """
    return name.lower().replace("mg", "").strip()


def as_set(names: Iterable[str]) -> set[str]:
    return {normalize(n) for n in names if n and n.strip()}


@dataclass(frozen=True)
class ImageScore:
    image: str
    true_positives: int
    false_positives: int
    false_negatives: int
    exact_match: bool

    @property
    def precision(self) -> float:
        """Of what we reported, how much was right.

        An empty prediction against an empty truth scores 1.0 - the pipeline
        correctly found nothing. An empty prediction against a non-empty truth
        is handled by recall, not here.
        """
        predicted = self.true_positives + self.false_positives
        if predicted == 0:
            return 1.0 if self.false_negatives == 0 else 0.0
        return self.true_positives / predicted

    @property
    def recall(self) -> float:
        """Of what was actually prescribed, how much we found."""
        actual = self.true_positives + self.false_negatives
        if actual == 0:
            return 1.0 if self.false_positives == 0 else 0.0
        return self.true_positives / actual

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 0.0 if (p + r) == 0 else 2 * p * r / (p + r)


def score_image(image: str, predicted: Iterable[str], truth: Iterable[str]) -> ImageScore:
    pred, true = as_set(predicted), as_set(truth)
    return ImageScore(
        image=image,
        true_positives=len(pred & true),
        false_positives=len(pred - true),
        false_negatives=len(true - pred),
        exact_match=pred == true,
    )


@dataclass(frozen=True)
class Report:
    n: int
    micro_precision: float
    micro_recall: float
    micro_f1: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    exact_match_rate: float
    total_true_positives: int
    total_false_positives: int
    total_false_negatives: int

    def as_row(self, label: str) -> str:
        return (
            f"{label:<22} {self.n:>4}  {self.micro_precision:>6.3f} "
            f"{self.micro_recall:>7.3f} {self.micro_f1:>6.3f}  "
            f"{self.exact_match_rate:>7.3f}"
        )


def aggregate(scores: Sequence[ImageScore]) -> Report:
    """Combine per-image scores.

    Micro averaging pools every medicine into one calculation, so prescriptions
    listing more drugs count for more. Macro averages the per-image scores, so
    every prescription counts equally regardless of length. They answer
    different questions and it is worth reporting both - a large gap between
    them usually means performance depends on prescription length.
    """
    n = len(scores)
    if n == 0:
        return Report(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    tp = sum(s.true_positives for s in scores)
    fp = sum(s.false_positives for s in scores)
    fn = sum(s.false_negatives for s in scores)

    micro_p = 1.0 if (tp + fp) == 0 else tp / (tp + fp)
    micro_r = 1.0 if (tp + fn) == 0 else tp / (tp + fn)
    micro_f1 = 0.0 if (micro_p + micro_r) == 0 else 2 * micro_p * micro_r / (micro_p + micro_r)

    return Report(
        n=n,
        micro_precision=micro_p,
        micro_recall=micro_r,
        micro_f1=micro_f1,
        macro_precision=sum(s.precision for s in scores) / n,
        macro_recall=sum(s.recall for s in scores) / n,
        macro_f1=sum(s.f1 for s in scores) / n,
        exact_match_rate=sum(1 for s in scores if s.exact_match) / n,
        total_true_positives=tp,
        total_false_positives=fp,
        total_false_negatives=fn,
    )
