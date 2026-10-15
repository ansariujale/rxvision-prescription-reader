"""Fast medicine-name lookup for OCR output.

The problem this solves: matching one line of OCR text against ~254,000 drug
names with a fuzzy scorer takes about 3.5 seconds. Lines that happen to match a
drug exactly are fast, because the scorer short-circuits on a perfect score.
Lines that match nothing are the slow ones - and on a prescription most lines
are exactly that: the doctor's name, the address, dosage instructions.

Two ideas make it fast:

1. A character-trigram inverted index. Cut every drug name into overlapping
   three-character pieces and record which names contain each piece. To look
   something up, cut the query the same way, count how many pieces each name
   shares with it, and only run the expensive scorer on the few hundred that
   share the most. Trigrams are the right unit here because OCR damage is
   local - one wrong character destroys three trigrams and leaves the rest
   intact, so `Augrnentin` still overlaps heavily with `Augmentin`.

2. Dropping dosage-form words. Almost every name in the dataset ends in
   "Tablet", so `tab`, `let` and `abl` appear in ~60% of entries and carry no
   information. Removing them shrinks the index and sharpens matching.

   The stripping has to be *fuzzy* and *token-level*. Token-level because
   "clopilet", "ventab dxt" and "janumet" contain form words as substrings and
   must survive intact. Fuzzy because OCR gives you "tablel", and a plain regex
   strips the clean dataset but not the scanned text - which leaves the query
   carrying a junk token the dataset entry no longer has, and makes matching
   worse than doing nothing at all.

The index narrows the field; it never decides. The same scorer on the same
threshold still makes the actual call, so results are unchanged apart from the
candidates it never had to look at.
"""

from __future__ import annotations

import pickle
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from rapidfuzz import fuzz, process

# Dosage forms and packaging words. These describe how a drug is delivered, not
# which drug it is.
DOSAGE_FORMS = (
    "tablet", "tablets", "tab", "tabs",
    "capsule", "capsules", "cap", "caps",
    "syrup", "syrups", "liquid", "elixir", "suspension", "emulsion", "solution",
    "drop", "drops", "ointment", "cream", "creams", "gel", "gels",
    "spray", "sprays", "wash", "lotion", "powder", "granules",
    "injection", "injections", "inj", "infusion",
    "vial", "vials", "ampoule", "ampoules", "amp", "amps",
    "sachet", "sachets", "kit",
)
_FORM_SET = frozenset(DOSAGE_FORMS)

# Below this length a token is too easy to mistake for a form word, and the
# damage from wrongly deleting part of a drug name is worse than the noise from
# keeping a short one.
MIN_FUZZY_TOKEN_LEN = 4
FORM_MATCH_CUTOFF = 80

DEFAULT_TOP_K = 400
DEFAULT_THRESHOLD = 68
# Trigrams present in more than this fraction of names are near-useless as a
# filter. Dropping them shrinks the index; keeping the cut conservative avoids
# eroding recall.
DEFAULT_STOP_CUT = 0.10
# ...but a percentage alone is meaningless on a small dataset. At 12 names a
# 10% cut is 1.2, so any trigram shared by two names would be dropped and both
# would become unfindable. Nothing is discarded until it appears in at least
# this many names, whatever the percentage works out to.
MIN_STOP_COUNT = 50

_WHITESPACE = re.compile(r"\s+")

# Prescription lines rarely arrive as a bare drug name. They come numbered, or
# prefixed with the dosage form abbreviated to a letter, or with stray marks the
# OCR picked up from the paper:
#
#     "1. scata 25"      "t. catel 40"      "(af esocam- dgr"      "3) divaa od"
#
# All of that counts toward the similarity score and drags it down, which is why
# several correctly-read drugs were landing just under the threshold. Measured:
# 22 of 85 labelled medicines were legible in the OCR text but missed by the
# matcher, and this noise is a large part of why.
_LINE_NOISE = re.compile(
    r"""^(?:
          [^a-z0-9]+                 # leading brackets, dashes, stray marks
        | \d{1,2}\s*[.)\-:]\s*       # list numbering:  1.   2)   3-
        | (?:tabs?|caps?|inj|syp|susp|sol|oint)\s*[.\-]?\s+   # dosage abbreviations
        | [a-z]\s*[.\-]\s+           # single-letter prefix:  t.   c.   s.
      )+""",
    re.VERBOSE,
)

# Below this, a "line" is too short to be a drug name and matching it produces
# noise. Measured: 69 of 233 returns were three characters or shorter - 'x',
# '10', 'lad' - matched from letterhead fragments and stray numbers.
MIN_LINE_LENGTH = 6


def clean_ocr_line(line: str) -> str:
    """Strip prescription list markers and dosage abbreviations off a line.

    >>> clean_ocr_line("1. scata 25")
    'scata 25'
    >>> clean_ocr_line("t. catel 40")
    'catel 40'
    >>> clean_ocr_line("augmentin 625")
    'augmentin 625'

    Only leading noise goes. Stray words in the middle stay, and so do short
    words with no punctuation attached - stripping bare two-letter tokens would
    start eating real drug names:

    >>> clean_ocr_line("(af esocam- dgr")
    'af esocam- dgr'
    """
    cleaned = _LINE_NOISE.sub("", line.strip())
    return _WHITESPACE.sub(" ", cleaned).strip()


@lru_cache(maxsize=100_000)
def _is_dosage_form(token: str) -> bool:
    """True if this token is a dosage form, or OCR's best attempt at one.

    Cached because the dataset repeats the same few thousand tokens hundreds of
    thousands of times - "tablet" alone appears in about 150,000 names.
    """
    if token in _FORM_SET:
        return True
    if len(token) < MIN_FUZZY_TOKEN_LEN:
        return False
    return (
        process.extractOne(
            token, DOSAGE_FORMS, scorer=fuzz.ratio, score_cutoff=FORM_MATCH_CUTOFF
        )
        is not None
    )


def strip_dosage_form(text: str) -> str:
    """Remove dosage-form words, whole tokens only.

    >>> strip_dosage_form("augmentin 625 duo tablet")
    'augmentin 625 duo'
    >>> strip_dosage_form("dolo 650 tablel")      # OCR damage
    'dolo 650'
    >>> strip_dosage_form("clopilet")             # contains 'let', survives
    'clopilet'
    >>> strip_dosage_form("ventab dxt")           # contains 'tab', survives
    'ventab dxt'
    """
    kept = [t for t in text.split() if not _is_dosage_form(t)]
    return _WHITESPACE.sub(" ", " ".join(kept)).strip()


def normalize(text: str) -> str:
    """Lowercase and drop the 'mg' suffix, matching the existing pipeline."""
    return text.lower().replace("mg", "").strip()


def trigrams(text: str) -> set[str]:
    """Overlapping three-character pieces, padded so short names still index.

    >>> sorted(trigrams("dolo"))
    ['  d', ' do', 'dol', 'lo ', 'olo']
    """
    padded = f"  {text} "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


@dataclass(frozen=True)
class Match:
    medicine_id: int
    name: str
    """The catalogue's full product name, e.g. 'Augmentin 625 Duo Tablet'."""
    key: str
    """The stripped key the score was computed on, e.g. 'augmentin 625 duo'."""
    score: float
    """0 to 100."""


class MedicineIndex:
    """Trigram inverted index over the medicine catalogue.

    v2 change from the desktop version: every name carries its catalogue id, so a
    match can be linked back to the `medicines` row.
    """

    def __init__(
        self,
        names: list[str],
        ids: list[int] | None = None,
        top_k: int = DEFAULT_TOP_K,
        stop_cut: float = DEFAULT_STOP_CUT,
    ):
        self.original = list(names)
        self.ids = list(ids) if ids is not None else list(range(len(self.original)))
        if len(self.ids) != len(self.original):
            raise ValueError("ids and names must be the same length")
        self.top_k = top_k
        self.stop_cut = stop_cut

        # Two parallel lists: what we match against, and what we report back.
        # Stripping merges products ("azithral 500 tablet" and "azithral 500
        # injection" both become "azithral 500"), so the originals are kept.
        self.keys = [strip_dosage_form(normalize(n)) for n in self.original]

        self._postings: dict[str, np.ndarray] = {}
        self._build()

    def __len__(self) -> int:
        return len(self.original)

    def _build(self) -> None:
        raw: dict[str, list[int]] = defaultdict(list)
        for i, key in enumerate(self.keys):
            for gram in trigrams(key):
                raw[gram].append(i)

        limit = max(len(self.keys) * self.stop_cut, MIN_STOP_COUNT)
        self._postings = {
            gram: np.array(positions, dtype=np.int32)
            for gram, positions in raw.items()
            if len(positions) <= limit
        }

    def candidates(self, query: str, top_k: int | None = None) -> list[int]:
        """Positions of the names sharing the most trigrams with `query`.

        A filter, not an answer: it narrows ~254,000 names to a few hundred
        worth scoring properly.
        """
        lists = [self._postings[g] for g in trigrams(query) if g in self._postings]
        if not lists:
            return []
        positions, counts = np.unique(np.concatenate(lists), return_counts=True)
        k = min(top_k or self.top_k, len(positions))
        return [int(positions[i]) for i in np.argpartition(counts, -k)[-k:]]

    def _query(self, line: str, clean: bool) -> str:
        query = strip_dosage_form(normalize(line))
        return clean_ocr_line(query) if clean else query

    def match(
        self,
        line: str,
        threshold: float = DEFAULT_THRESHOLD,
        clean: bool = True,
        min_length: int = MIN_LINE_LENGTH,
    ) -> Match | None:
        """Best catalogue entry for one line of text, or None below threshold."""
        query = self._query(line, clean)
        if not query or len(query) < min_length:
            return None

        positions = self.candidates(query)
        if not positions:
            return None

        best = process.extractOne(
            query,
            [self.keys[p] for p in positions],
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
        )
        if best is None:
            return None
        _, score, at = best
        p = positions[at]
        return Match(self.ids[p], self.original[p], self.keys[p], float(score))

    def search(self, text: str, limit: int = 8) -> list[Match]:
        """Ranked suggestions for autocomplete.

        Unlike `match` this has no threshold and blends in a prefix-friendly
        scorer, because a user typing "augm" expects Augmentin at the top.
        """
        query = normalize(text).strip()
        if len(query) < 2:
            return []
        positions = self.candidates(query, top_k=max(self.top_k, 600))
        if not positions:
            return []
        choices = {p: self.original[p].lower() for p in positions}
        ranked = process.extract(
            query, choices, scorer=fuzz.WRatio, limit=limit * 3, score_cutoff=40
        )
        seen: set[str] = set()
        out: list[Match] = []
        for _, score, p in ranked:
            # Prefix hits first, then by score.
            bonus = 15 if choices[p].startswith(query) else 0
            out.append(Match(self.ids[p], self.original[p], self.keys[p], min(100.0, score + bonus)))
        out.sort(key=lambda m: m.score, reverse=True)
        unique = []
        for m in out:
            if m.name in seen:
                continue
            seen.add(m.name)
            unique.append(m)
        return unique[:limit]

    # -- persistence -------------------------------------------------------
    # Building costs ~46 s on the full dataset, mostly fuzzy-stripping. Cached
    # to disk, it reloads in ~0.2 s.

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("wb") as f:
            pickle.dump(
                {
                    "original": self.original,
                    "ids": self.ids,
                    "keys": self.keys,
                    "postings": self._postings,
                    "top_k": self.top_k,
                    "stop_cut": self.stop_cut,
                },
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        tmp.replace(path)

    @classmethod
    def load(cls, path: str | Path) -> "MedicineIndex":
        with Path(path).open("rb") as f:
            data = pickle.load(f)
        index = cls.__new__(cls)
        index.original = data["original"]
        index.ids = data["ids"]
        index.keys = data["keys"]
        index._postings = data["postings"]
        index.top_k = data["top_k"]
        index.stop_cut = data["stop_cut"]
        return index
