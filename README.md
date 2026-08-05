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

That's why there's no model in this repo, and why the system's accuracy is mostly a function of
how well the image is cleaned up before anything is sent anywhere.

## How it works

```
photo
  ↓
crop window (manual region select)
  ↓
OpenCV preprocessing
  ↓
Tesseract OCR ──► mean confidence
  ↓                     │
  │             < 70? ──┴──► AWS Textract
  ↓                             ↓
  └─────────► extracted text ◄──┘
                    ↓
      RapidFuzz match vs. medicine dataset
      (token_sort_ratio, threshold 68)
                    ↓
          medicine details via HTTP lookup
                    ↓
                results pane
```

**Preprocessing** (`preprocessing.py`) does grayscale, adaptive Gaussian thresholding, Canny edge
detection overlaid back onto the original, then noise removal through dilate / erode /
morphological close / median blur. Erosion and dilation are applied conditionally on the number
of connected components in the binary image, so a sparse scan doesn't get eroded into nothing and
a dense one gets thinned.

**OCR routing** (`text_extraction.py`) runs Tesseract first with `--oem 3 --psm 6` and reads back
its per-word confidence scores. If mean confidence is under 70, the image goes to AWS Textract
instead. Tesseract is local and free, so it handles the clean images and only the hard ones cost
an API call.

**Matching** (`text_extraction.py`) compares each extracted line against a medicine-name dataset
using RapidFuzz's `token_sort_ratio`, keeping matches at 68 or above. This is what recovers a
drug name when OCR gets a character or two wrong, which on handwriting it usually does.

## Stack

Python, PyQt6, OpenCV, pytesseract, AWS Textract (boto3), RapidFuzz, pandas, requests.

Google Cloud Vision is wired up and was the original escalation target, but that call path is
currently commented out in favour of Textract — see Known issues.

## Setup

Needs Python 3.10+ and Tesseract installed and on `PATH`.

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

Three things aren't in the repo and you'll need to supply them:

1. **`resource/medicine_names.csv`** — the drug dataset the matcher reads. The matcher uses the
   `name` column; the file also carries `id`, `price(₹)`, `manufacturer_name`, `type`,
   `pack_size_label` and composition columns. Left out because it's ~31 MB of third-party data.
2. **AWS credentials** with Textract access in `ap-south-1`, through the normal boto3 chain
   (`~/.aws/credentials` or environment variables).
3. **`resource/client_secret_code1.json`** — a Google Cloud service-account key. Still required at
   import even though the Vision path is disabled.

```bash
python ocrApp.py
```

## Known issues

Real ones, in the code as it stands:

- **Google Vision is a required dependency that does nothing.** `text_extraction.py` builds an
  `ImageAnnotatorClient` at module import, so the app won't start without a service-account JSON —
  but the Vision call is commented out and Textract handles every escalation. The client should
  either be created lazily or the Vision path restored.
- **Preprocessing can crash on dark images.** Step 7 sets the output path to
  `temp/eroded_image.jpg` when the mean pixel value is below 120, but nothing ever writes that
  file, so the next stage opens a path that isn't there.
- **Preprocessing can throw away its own work.** The rotation step operates on the *original*
  image rather than the processed one, and when it rotates a portrait image it returns that as the
  final path — discarding the grayscale, threshold and noise-removal stages entirely.
- **The medicine lookup URL is hardcoded** in `api_handler.py` instead of configured.
- **No accuracy measurement.** I have no labelled test set for this, so there's no OCR accuracy
  number I can stand behind. Any figure quoted without one would be a guess.
- **No tests.**

## Possible next steps

Fix the two preprocessing bugs, make the Vision client lazy or drop it, move the lookup URL and
the confidence and matching thresholds into config, and put together a small labelled set of
prescription images so the pipeline can be measured instead of eyeballed.
