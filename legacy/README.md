# RxVision — Handwritten Prescription Reader

A desktop application that reads photographs of handwritten medical prescriptions and pulls out
the medicine names, using image preprocessing, OCR, and fuzzy matching against a drug database.

Handwritten prescriptions are hard to digitise. The handwriting is often poor, photos get taken
in bad light at odd angles, and drug names are long, similar to one another, and full of
abbreviations. General-purpose OCR pointed at a raw photo of one is close to useless. Most of the
work here is in what happens before and after the OCR call.

## Attribution

This was a two-person project, originally developed at
[Pjanhavi24/RxVision-ocr-prescription-reader](https://github.com/Pjanhavi24/RxVision-ocr-prescription-reader)
with [@Pjanhavi24](https://github.com/Pjanhavi24), who owned that repository and reviewed and
merged the work.

This repo is my own copy of the implementation, with the commit history kept intact so the split
is checkable rather than something you have to take my word for. By `git blame` at the current
head I wrote **1,729 of 1,851 lines of Python (93%)**, across 45 of the 100 commits:

| File | My lines | Total |
|---|---:|---:|
| `ocrApp.py` — Qt application and UI flow | 886 | 891 |
| `preprocessing.py` — OpenCV pipeline | 264 | 264 |
| `crop.py` — interactive crop window | 201 | 201 |
| `text_extraction.py` — OCR routing and matching | 140 | 140 |
| `open_file_dialog.py` | 87 | 87 |
| `loading.py` | 54 | 117 |
| `api_handler.py` — medicine lookup | 51 | 51 |
| `process_and_extract.py` | 24 | 24 |
| `switchpages.py` | 22 | 22 |
| `check_internet.py` | 0 | 54 |

The build artifacts that had been committed to the original repo (a 90 MB `.exe`, a 96 MB `.zip`,
and PyInstaller `build/` output) are stripped from this history, which is why this clones at 9 MB
rather than 238 MB.

## Why cloud OCR instead of a trained model

The original plan was to train a handwriting recognition model. I dropped it once I worked out
what it would actually take — a labelled corpus of real prescriptions I didn't have, and training
time that wasn't realistic on one laptop. Rather than spend the project on a model that would
have ended up worse than an off-the-shelf one, I used managed OCR services and put the effort
into preprocessing and post-processing instead.

That's why there's no model in this repo. I expected accuracy to mostly come down to
preprocessing, but measurement showed otherwise — see [Measuring it](#measuring-it) below.

## How it works

```
photo
  ↓
crop window (manual region select)
  ↓
AWS Textract
  ↓
RapidFuzz match vs. medicine dataset
(token_sort_ratio, threshold 68)
  ↓
medicine details via HTTP lookup
  ↓
results pane
```

**OCR** (`text_extraction.py`) sends the image straight to AWS Textract. It used to try Tesseract
first and only escalate to Textract below a confidence threshold, but measurement
([`docs/evaluation-log.md`](docs/evaluation-log.md)) found Tesseract read zero of 85 medicines on
real handwritten prescriptions and its confidence score didn't predict that failure, so there was
no signal left to route on.

`preprocessing.py` still exists — grayscale, adaptive Gaussian thresholding, Canny edge detection,
noise removal through dilate / erode / morphological close / median blur, erosion and dilation
applied conditionally on connected-component count — but nothing in the live pipeline calls it any
more. It was built for Tesseract, and the eval log's own preprocessed-vs-original comparison for
Textract was inconclusive on 5 images. Kept in case a local-OCR path comes back.

**Matching** (`text_extraction.py`) compares each extracted line against a medicine-name dataset
using RapidFuzz's `token_sort_ratio`, keeping matches at 68 or above. This is what recovers a
drug name when OCR gets a character or two wrong, which on handwriting it usually does.

**Lookup** (`api_handler.py`) strips dosage-form words like "tablet" and "syrup" off the matched
name, then queries a medicines API for the details shown in the results pane. That API is one I
deploy myself — originally hosted on Railway, later moved to AWS Lambda behind API Gateway in
`ap-south-1`.

## Stack

Python, PyQt6, OpenCV, AWS Textract (boto3), RapidFuzz, pandas, requests. The medicine lookup
service behind it runs on AWS Lambda and API Gateway.

pytesseract is still a dependency of the [`eval/`](eval/) harness, which measures Tesseract
against Textract for comparison, but the app itself no longer calls it.

Google Cloud Vision was the original escalation target before I moved to Textract. It has since
been removed — it was still being imported and authenticated at startup despite nothing calling
it, which meant the app refused to start without a service-account key it never used.

## Setup

Needs Python 3.10+. Tesseract on `PATH` is only needed to run the [`eval/`](eval/) harness, not
the app itself.

```bash
git clone https://github.com/ansariujale/rxvision-prescription-reader.git
```

```bash
cd rxvision-prescription-reader
```

```bash
python -m venv .venv
```

Activate it — `.venv\Scripts\activate` on Windows, `source .venv/bin/activate` otherwise — then:

```bash
pip install -r requirements.txt
```

Two things aren't in the repo and you'll need to supply them:

1. **`resource/medicine_names.csv`** — the drug dataset the matcher reads. The matcher uses the
   `name` column; the file also carries `id`, `price(₹)`, `manufacturer_name`, `type`,
   `pack_size_label` and composition columns. Left out because it's ~31 MB of third-party data.
2. **AWS credentials** with Textract access in `ap-south-1`, through the normal boto3 chain
   (`~/.aws/credentials` or environment variables).

```bash
python ocrApp.py
```

## Measuring it

There's an evaluation harness in [`eval/`](eval/) that scores medicine extraction against a
labelled set and compares the three ways of routing between the OCR engines — Tesseract only,
Textract only, and escalating between them at a confidence threshold. It runs both engines once
per image and caches everything, so every routing strategy and threshold can be compared offline
without re-paying for API calls.

On 30 hand-labelled real prescriptions (85 medicines):

| | precision | recall | f1 |
|---|---:|---:|---:|
| tesseract only | 0.000 | 0.000 | 0.000 |
| textract only | 0.052 | 0.129 | 0.074 |
| escalate at 70 | 0.035 | 0.071 | 0.047 |

Tesseract read zero of the 85 medicines from these images, so the confidence-based escalation
buys nothing and is actually worse than calling Textract every time — it keeps Tesseract's empty
result on 27% of images. The bigger ceiling is OCR itself: on some prescriptions, none of the
labelled drugs appear anywhere in the raw OCR text, which no amount of matcher tuning can recover.

Full write-up, methodology, and what I tried next is in
[`docs/evaluation-log.md`](docs/evaluation-log.md). 30 labelled prescriptions is a small sample —
labelling more, with a proper tune/holdout split, is the next piece of work.

## Possible next steps

Label a set of prescriptions and run the harness, move the lookup URL and the two thresholds into
config, and profile the matching stage — `match_medicine` re-normalises the entire 254k-name
dataset on every line of OCR output, which is almost certainly where the time goes.
