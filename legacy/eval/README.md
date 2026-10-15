# Evaluation harness

Measures how well the pipeline actually extracts medicine names, and compares
the three ways of routing between the OCR engines.

Nothing here has been run against real prescriptions yet, so there are no
numbers in this repo to quote. That is the point of building it — the accuracy
figures come from running this, not from estimating.

## Prescription images are patient data

Real prescriptions carry patient names, doctor names, dates, sometimes phone
numbers. `eval/images/`, `eval/cache/` and `eval/labels.csv` are all gitignored
and must stay that way. Only `labels.example.csv` is committed, and it contains
made-up rows.

## Why it's split into two stages

Textract charges per call. If scoring re-ran OCR every time, every experiment
would cost money and you'd avoid experimenting — which is how thresholds end up
being guesses.

So `ocr_runner.py` runs **both** engines on **every** image once and caches
everything: raw text, Tesseract's confidence, per-stage timings. `evaluate.py`
then derives every routing strategy from that cache, offline and free:

| Mode | Rule |
|---|---|
| `tesseract-only` | always use the Tesseract text |
| `textract-only` | always use the Textract text |
| `escalate@T` | Tesseract when its confidence ≥ T, otherwise Textract |

Escalation at T=0 is Tesseract-only and at T=100 is Textract-only, so a sweep
brackets both baselines and shows exactly what the routing is buying — in
accuracy gained and API calls spent.

## Preparing a dataset

Aim for 50+ images. Below about 30 the error bars are wide enough that the
number doesn't mean much.

Label them **blind** — write down what the prescription says before looking at
what the pipeline produced, or you'll unconsciously ratify its mistakes.

Use the canonical names from `resource/medicine_names.csv` wherever the drug
appears there. The pipeline returns entries from that dataset, so ground truth
has to speak the same vocabulary or you're measuring formatting differences
instead of OCR quality. Where a prescribed drug isn't in the dataset at all,
record it anyway — "the right answer was unreachable" is a different failure
from "OCR misread it", and you want to be able to tell them apart.

`eval/labels.csv`, pipe-separated, empty means nothing legible:

```csv
image,medicines
rx_001.jpg,Augmentin 625 Duo Tablet|Pantop 40 Tablet
rx_002.jpg,
```

**Split it.** Tune thresholds on part of the set and report the final number on
a part you haven't touched. Tuning and reporting on the same images produces a
figure that is optimistic by an unknown amount.

## Running it

```bash
python -m eval.ocr_runner --images eval/images
```

Both engines, every image, cached to `eval/cache/ocr_results.json` after each
one — so an interrupt doesn't lose calls you've paid for. Re-running skips
anything already cached. Add `--mock` to exercise the plumbing with stub
engines and no Tesseract or AWS at all.

```bash
python -m eval.evaluate --labels eval/labels.csv
```

```bash
python -m eval.evaluate --labels eval/labels.csv --sweep
```

## Reading the output

- **precision** — of the medicines reported, how many were real. Low precision
  means invented drug names, which is worse than missing one.
- **recall** — of the medicines actually prescribed, how many were found.
- **exact** — share of prescriptions where the *entire* set was right. The
  strictest measure and the closest to "would a pharmacist trust this".
- **textract** — share of images that cost an API call.

Both micro and macro averages are computed. Micro pools every medicine, so
longer prescriptions count for more; macro weights each prescription equally.
A large gap between them means performance depends on prescription length.

## Note on `matching.py`

It's a copy of `match_medicine` from `text_extraction.py` with one change: the
dataset normalisation is hoisted out of the per-line loop. Production
re-normalises all ~254,000 names for every line of OCR output, which makes
sweeps unusable.

Hoisting a loop-invariant can't change the result, and
`tests/test_matching.py` asserts the two functions agree across a range of
inputs and thresholds. If that test fails, this copy is wrong.

## Tests

```bash
pytest
```

37 tests over the scoring and matching logic. No images, no engines, no network.
