"""Stage 1: run every OCR engine over every image, once, and cache the result.

This is the only part that costs money. It runs Tesseract *and* Textract on
each image unconditionally, rather than escalating, because caching both means
every routing strategy can be evaluated offline afterwards from the same data:
Tesseract-only, Textract-only, and escalation at any confidence threshold.
Doing it the other way round would mean re-paying for every experiment.

The cache is keyed by image name and written after each image, so an
interrupted run resumes instead of starting over.

    python -m eval.ocr_runner --images eval/images
    python -m eval.ocr_runner --images eval/images --engines tesseract
    python -m eval.ocr_runner --images eval/images --mock      # no engines needed
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def _timed(fn, *args, **kwargs):
    """Run fn, returning (result, elapsed_seconds, error_or_None)."""
    start = time.perf_counter()
    try:
        return fn(*args, **kwargs), time.perf_counter() - start, None
    except Exception as e:
        return None, time.perf_counter() - start, f"{type(e).__name__}: {e}"


def mean_confidence(conf_values) -> tuple[float, int]:
    """Mean Tesseract confidence over recognised words. Returns (mean, count).

    Tesseract's TSV output has a row per page, block, paragraph and line as
    well as per word, and the structural rows carry a confidence of -1. Those
    have to come out before averaging or the mean is dragged toward zero in
    proportion to how much structure the page has.

    Kept as a separate function because the production copy of this got it
    wrong in a way that was invisible: it filtered on the *string* '-1' while
    pytesseract returns ints, so the filter never matched anything.
    """
    scores = [int(c) for c in conf_values if int(c) != -1]
    return (sum(scores) / len(scores) if scores else 0.0), len(scores)


def preprocess(image_path: str) -> str:
    from preprocessing import process_image

    out = process_image(image_path)
    if not out or not Path(out).exists():
        raise RuntimeError(f"preprocessing returned a missing path: {out!r}")
    return out


def run_tesseract(processed_path: str) -> dict:
    """Text plus the mean per-word confidence used for escalation decisions."""
    import os

    import pytesseract
    from PIL import Image

    # On Windows the installer often puts tesseract.exe somewhere that isn't on
    # PATH for every shell, and pytesseract just reports "not installed".
    # TESSERACT_CMD lets you point at it directly.
    tesseract_cmd = os.environ.get("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    image = Image.open(processed_path)
    text = pytesseract.image_to_string(image, lang="eng", config=r"--oem 3 --psm 6")

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    confidence, words = mean_confidence(data["conf"])

    return {"text": text, "confidence": confidence, "words": words}


def run_textract(original_path: str) -> dict:
    """Textract reads the original image, not the preprocessed one.

    That mirrors production: extract_text_with_textract() is handed the source
    path. Textract does its own preprocessing internally and generally does
    better on an unmodified photo.
    """
    import boto3

    client = boto3.client("textract", region_name="ap-south-1")
    with open(original_path, "rb") as f:
        response = client.detect_document_text(Document={"Bytes": f.read()})

    lines = [b["Text"] for b in response["Blocks"] if b["BlockType"] == "LINE"]
    return {"text": "\n".join(lines), "blocks": len(response["Blocks"])}


def mock_tesseract(processed_path: str) -> dict:
    """Deterministic stand-in so the harness can be exercised without engines."""
    name = Path(processed_path).stem
    return {"text": f"augmentin 625 duo tablet\nunreadable scrawl\n{name}", "confidence": 55.0, "words": 8}


def mock_textract(original_path: str) -> dict:
    name = Path(original_path).stem
    return {"text": f"Augmentin 625 Duo Tablet\nPantop 40 Tablet\n{name}", "blocks": 12}


def process_one(image_path: Path, engines: set[str], mock: bool) -> dict:
    record: dict = {"image": image_path.name, "engines": {}}

    processed, elapsed, error = _timed(preprocess, str(image_path))
    record["preprocess"] = {"seconds": round(elapsed, 4), "error": error, "output": processed}
    if error:
        # Without a preprocessed image Tesseract has nothing to read, but
        # Textract works off the original so it can still run.
        processed = None

    if "tesseract" in engines:
        fn = mock_tesseract if mock else run_tesseract
        if processed is None:
            record["engines"]["tesseract"] = {"error": "preprocessing failed", "seconds": 0.0}
        else:
            result, elapsed, error = _timed(fn, processed)
            record["engines"]["tesseract"] = {
                **(result or {}),
                "seconds": round(elapsed, 4),
                "error": error,
            }

    if "textract" in engines:
        fn = mock_textract if mock else run_textract
        result, elapsed, error = _timed(fn, str(image_path))
        record["engines"]["textract"] = {
            **(result or {}),
            "seconds": round(elapsed, 4),
            "error": error,
        }

    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", default="eval/images", help="directory of prescription images")
    parser.add_argument("--cache", default="eval/cache/ocr_results.json")
    parser.add_argument("--engines", default="tesseract,textract")
    parser.add_argument("--mock", action="store_true", help="use stub engines; no Tesseract or AWS needed")
    parser.add_argument("--force", action="store_true", help="re-run images already in the cache")
    args = parser.parse_args()

    engines = {e.strip() for e in args.engines.split(",") if e.strip()}
    images_dir = Path(args.images)
    cache_path = Path(args.cache)

    if not images_dir.is_dir():
        print(f"no such directory: {images_dir}")
        return 1

    images = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        print(f"no images found in {images_dir}")
        return 1

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache: dict = {}
    if cache_path.exists() and not args.force:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    todo = [p for p in images if p.name not in cache]
    print(f"{len(images)} images, {len(cache)} already cached, {len(todo)} to run")
    if args.mock:
        print("MOCK MODE - stub engines, results are not real")

    for i, image_path in enumerate(todo, 1):
        print(f"  [{i}/{len(todo)}] {image_path.name}", flush=True)
        cache[image_path.name] = process_one(image_path, engines, args.mock)
        # Written every iteration so a crash or an interrupt doesn't lose paid calls.
        cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")

    failures = [
        (name, engine, data["error"])
        for name, rec in cache.items()
        for engine, data in rec.get("engines", {}).items()
        if data.get("error")
    ]
    print(f"\ncached {len(cache)} images to {cache_path}")
    if failures:
        print(f"{len(failures)} engine failures:")
        for name, engine, err in failures[:10]:
            print(f"  {name} [{engine}] {err}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
