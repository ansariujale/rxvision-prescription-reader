# Evaluation log

A record of every measurement run against this project: what was asked, how it
was configured, what came back, and what changed as a result.

It exists so claims about this system can be checked rather than taken on
trust, and so the next iteration starts from what is already known instead of
from guesses. Runs are listed oldest first.

Every number here came from running the code. Where a result was inconclusive
or a hypothesis was wrong, that is recorded too.

## Environment

| | |
|---|---|
| OS | Windows 11 |
| Python | 3.13.14 |
| Tesseract | 5.5.3.20260724 |
| AWS Textract | `detect_document_text`, region `ap-south-1` |
| OpenCV | 5.0.0 |
| rapidfuzz | 3.x |
| Medicine dataset | 253,973 Indian drug names (`resource/medicine_names.csv`) |

## Reproducing any of it

```bash
python -m eval.check_setup
```

```bash
python -m eval.ocr_runner --images eval/images
```

```bash
python -m eval.evaluate --labels eval/labels.csv --sweep
```

`ocr_runner` is the only stage that costs money. It runs both engines on every
image once and caches the output, so every routing strategy below was scored
offline from the same cache without re-paying.

---

## Run 1 — Tesseract confidence was being computed wrong

**Question.** A clean, machine-printed test page was escalating to Textract.
Why, when Tesseract read it perfectly?

**Method.** Compared the per-word confidence values Tesseract returns against
what `get_tesseract_confidence` computed from them.

**Result.**

| | |
|---|---|
| Mean over all 24 returned rows | 43.1 |
| Mean over the 11 real word rows | 95.3 |

**Cause.** Tesseract's output has a row per page, block, paragraph and line as
well as per word; the structural rows carry a confidence of `-1`. The filter
meant to drop them compared each value against the *string* `'-1'`, but
pytesseract returns ints, so nothing was ever filtered.

**Consequence.** The escalation threshold is 70. A page scoring a true 95 was
reported as 43, so it escalated. In practice every image was being sent to
Textract regardless of how well Tesseract had done — the cost-saving routing
had never once engaged.

**Action.** Fixed in `text_extraction.py`; regression tests in
`eval/tests/test_confidence.py`.

---

## Run 2 — The inversion preprocessing step was harming OCR

**Question.** Refactoring the preprocessing chain turned `invert_image` from a
step whose output was discarded into one that fed the rest of the pipeline.
Did that help or hurt?

**Method.** Same synthetic printed page through both chains, OCR'd with
Tesseract, compared text and mean confidence.

**Result.**

| Configuration | OCR output | Confidence | Exact |
|---|---|---:|---|
| With inversion | `Augmentin625 DuojTablet` | 33.0 | no |
| Without inversion | `Augmentin 625 Duo Tablet` | 95.5 | yes |

**Interpretation.** Tesseract expects dark text on a light background.
Inverting produces the opposite. The 33.0 also sits below the escalation
threshold, so every image would have been pushed to paid Textract.

**Action.** `invert_image` removed from `PREPROCESSING_STEPS`. Kept as a
function for genuinely inverted scans.

---

## Run 3 — Making medicine matching fast enough to evaluate

**Question.** Matching one line of OCR text against 253,973 names took ~3.5 s.
A single evaluation pass was projected at ~28 minutes and a threshold sweep at
over two hours, which made experimenting impractical. What actually helps?

**Method.** Timed a single `process.extractOne` call. Lines matching a drug
exactly are fast because the scorer short-circuits at 100; lines matching
nothing must scan everything. Most lines on a prescription are the second kind,
so all measurements used a non-matching line as the worst case.

**Attempts that did not work.** Recorded because they were the majority.

| Attempt | Result |
|---|---|
| `score_cutoff=68` | **slower** — 6.3 s vs 4.7 s |
| Pre-sorting tokens once | 1.1–2× |
| `process.cdist` with `workers=-1` (8 cores) | **slower** — 0.8× |
| Length-band candidate pruning | 1.1× — drug names cluster in a narrow band |
| Deduplicating the dataset | only 2% duplicates |

**What worked.** A character-trigram inverted index: index every name by its
overlapping three-character substrings, then run the expensive scorer only on
the few hundred names sharing the most trigrams.

| Configuration | Speedup | Missed matches |
|---|---:|---|
| Trigram index, all trigrams, top-400 | 150× | 0 / 60 |
| + stop-trigrams dropped (>10% of names), top-400 | **497×** | 0 / 60 |
| + top-400 reduced to 200 | 817× | 1 / 60 |
| + top-400 reduced to 100 | 1072× | 1 / 60 |

Below top-400 recall starts to go, so 400 is the floor.

**Dosage-form stripping.** Nearly every dataset entry ends in "Tablet", so
`tab`, `let` and `abl` appear in ~60% of names and filter nothing. Stripping
those words improved both speed and accuracy — but only when done correctly:

| Configuration | Correct | ms/query |
|---|---:|---:|
| Full names, all trigrams | 42 / 50 | 30.2 |
| Full names, stop-trigrams dropped | 42 / 50 | 11.7 |
| Regex-stripped dosage forms | **34 / 50** | 8.3 |
| **Fuzzy-stripped dosage forms** | **46 / 50** | 9.2 |
| Fuzzy-stripped + stop-trigrams dropped | 46 / 50 | **7.4** |

The regex version made accuracy *worse*. It strips `tablet` from the clean
dataset but not `tablel` from OCR output, leaving the query carrying a token
the dataset entry no longer has. The stripper has to be fuzzy on both sides.

Stripping must also be token-level: removing `tab` as a substring destroys
`ventab dxt`, and `let` destroys `clopilet`.

**Measured on the real dataset**, not the benchmark subset:

| | Brute force | Trigram index |
|---|---:|---:|
| Per line | ~3,500 ms | **11.5 ms** |
| Correct on 25 corrupted names | 21 / 25 | **21 / 25 — identical** |
| Time for those 25 | 63.8 s | 0.2 s |
| Index build | — | 46 s, cached to disk, reloads in 0.2 s |

**Limitation.** The index is a heuristic filter, not an exhaustive search. Zero
misses across 60 corrupted names means the true miss rate is probably under 5%,
not that it is zero. A provable bound exists via minimum-overlap thresholds;
this uses the measured route.

**Action.** Implemented as `medicine_index.py`, 41 tests. `evaluate.py --exact`
falls back to brute force for verification.

---

## Run 4 — Textract on the original vs the preprocessed image

**Question.** Production sends Textract the binarised, denoised image. Textract
does its own preprocessing internally, so would the original photo do better?

**Method.** 5 real prescriptions, both configurations, counting medicines found.

**Result.**

| Image | Textract on original | Textract on processed |
|---|---:|---:|
| rx_3 | 13 | 12 |
| rx_4 | 1 | 1 |
| rx_5 | 6 | 8 |

**Conclusion: inconclusive.** Three usable images, split roughly evenly,
differences of one or two. The hypothesis was neither supported nor refuted —
five images cannot answer it. No change made.

---

## Run 5 — Full evaluation, 30 hand-labelled prescriptions

The first measurement of the system as a whole.

**Dataset.** 30 real prescriptions, labelled by hand before looking at any OCR
output. 85 medicines total, mean 2.8 per prescription, 4 prescriptions with
none legible.

**Label reachability.** Checked first, because a drug absent from the dataset
can never be returned:

| | Count | Share |
|---|---:|---:|
| Exactly present in the dataset | 63 | 74% |
| Close match present | 8 | 9% |
| **Not in the dataset at all** | **14** | **16%** |

Unreachable examples: `D-Task 60k`, `Cefadox-Xl 200`, `Nervmax Nt`,
`L.S Belt` (a support belt, not a drug), `Hexabenz Spray`.

So 83% of labels were reachable — vocabulary is not the main limitation.

**Results.** Scoring is per-prescription set comparison, micro-averaged.

| Mode | Precision | Recall | F1 | Exact set | Textract calls |
|---|---:|---:|---:|---:|---:|
| tesseract-only | 0.000 | 0.000 | 0.000 | 0.100 | 0% |
| textract-only | 0.052 | **0.129** | 0.074 | 0.033 | 100% |
| escalate@70 | 0.035 | 0.071 | 0.047 | 0.000 | 73% |

**Findings.**

1. **Tesseract found zero medicines across all 30 prescriptions.** The
   confidence-based escalation has no cost case, because there is nothing to
   save by using Tesseract. Escalation at 70 scores *worse* than always using
   Textract, since on 27% of images it keeps Tesseract's empty output.

2. **OCR frequently fails to read the handwriting at all.** For `rx_3`, none of
   the six labelled drugs appear anywhere in Textract's raw text. This is the
   ceiling on the approach — no matcher improvement can recover words that were
   never read.

3. **The matcher produces substantial false positives.** Of 233 returns, 69
   were three characters or shorter — `'x'`, `'10'`, `'lad'` — fragments of
   letterheads and stray numbers matching short drug names.

**Follow-up: minimum line length.** Refusing to match very short lines:

| Min length | Precision | Recall | F1 |
|---:|---:|---:|---:|
| 0 (current) | 0.052 | 0.129 | 0.074 |
| 4 | 0.070 | 0.129 | 0.091 |
| 6 | 0.085 | 0.118 | 0.099 |
| 8 | 0.095 | 0.094 | 0.095 |
| 10 | 0.119 | 0.082 | 0.097 |

Precision more than doubles at length 10 but recall falls; F1 stays flat around
0.09. A real improvement, not a rescue.

**Limitations of this run.** 30 prescriptions is a small sample — treat these as
order-of-magnitude, not precise. Labels were not split into tune and holdout
sets, so any threshold chosen from this data would be optimistic. Textract was
given the original image, which differs from production.

---

## Where this leaves the project

Measured, on 30 real prescriptions: **12.9% recall, 5.2% precision** at best.
The system finds roughly one prescribed medicine in eight, and most of what it
reports is wrong.

The bottleneck is OCR on handwriting, not matching or speed. Both of those have
been improved substantially and neither is what limits the result.

**Consequences for what can be claimed.** No accuracy figure for this project
can be stated other than the one above. Any previously quoted number was not
measured and is contradicted by this data.

**Next steps, in order of expected value:**

1. Remove the confidence-based escalation — measurably worse than using
   Textract directly.
2. Add the minimum-line-length filter — doubles precision at no cost.
3. Investigate handwriting-specific OCR, or scope the project explicitly to
   printed prescriptions, which is an honest and documentable limitation.
4. Re-label with a tune/holdout split before tuning any threshold on this data.
