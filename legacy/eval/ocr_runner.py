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


def preprocess(image_path: str):
    """Run the app's preprocessing chain and return the image itself.

    process_image returns a numpy array rather than a temp-file path, so there
    is nothing on disk to check for. `is None` rather than a truth test: a
    numpy array raises on `if not array`.
    """
    from preprocessing import process_image

    out = process_image(image_path)
    if out is None:
        raise RuntimeError("preprocessing returned None")
    return out


def run_tesseract(processed_image) -> dict:
    """Text plus the mean per-word confidence used for escalation decisions."""
    import os

    import pytesseract

    # On Windows the installer often puts tesseract.exe somewhere that isn't on
    # PATH for every shell, and pytesseract just reports "not installed".
    # TESSERACT_CMD lets you point at it directly.
    tesseract_cmd = os.environ.get("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    text = pytesseract.image_to_string(processed_image, lang="eng", config=r"--oem 3 --psm 6")

    data = pytesseract.image_to_data(processed_image, output_type=pytesseract.Output.DICT)
    confidence, words = mean_confidence(data["conf"])

    return {"text": text, "confidence": confidence, "words": words}


def run_textract(original_path: str) -> dict:
    """Textract reads the ORIGINAL image, not the preprocessed one.

    This deliberately differs from production. process_and_extract.py currently
    hands extract_text_with_textract() the *preprocessed* path, so in the app
    Textract receives a binarised, eroded, denoised image. Textract does its own
    preprocessing internally and is generally stronger on an unmodified photo,
    so passing the original is very likely the better configuration.

    So this measures Textract closer to its best rather than as the app runs it
    today. That is the comparison worth having, but it is a real difference and
    the results should be read knowing it.
    """
    import boto3

    client = boto3.client("textract", region_name="ap-south-1")
    with open(original_path, "rb") as f:
        response = client.detect_document_text(Document={"Bytes": f.read()})

    lines = [b["Text"] for b in response["Blocks"] if b["BlockType"] == "LINE"]
    return {"text": "\n".join(lines), "blocks": len(response["Blocks"])}


def mock_tesseract(processed_image) -> dict:
    """Deterministic stand-in so the harness can be exercised without engines."""
    return {
        "text": "augmentin 625 duo tablet\nunreadable scrawl",
        "confidence": 55.0,
        "words": 8,
    }


def mock_textract(original_path: str) -> dict:
    name = Path(original_path).stem
    return {"text": f"Augmentin 625 Duo Tablet\nPantop 40 Tablet\n{name}", "blocks": 12}


def needs_run(record: dict | None, engines: set[str]) -> bool:
    """True if this image still has work to do.

    An image counts as done only when every requested engine produced a result
    without an error. Caching a failure and then skipping it forever was the
    original behaviour, and it meant a transient problem - a missing Tesseract
    binary, an expired AWS token - got baked into the cache permanently and
    re-reported on every subsequent run as though it had just happened.
    """
    if record is None:
        return True
    results = record.get("engines", {})
    return any(
        engine not in results or results[engine].get("error")
        for engine in engines
    )


def engine_failures(cache: dict) -> list[tuple[str, str, str]]:
    return [
        (name, engine, data["error"])
        for name, rec in cache.items()
        for engine, data in rec.get("engines", {}).items()
        if data.get("error")
    ]


def process_one(image_path: Path, engines: set[str], mock: bool, existing: dict | None = None) -> dict:
    # Start from whatever is already cached. Re-running --engines tesseract
    # must not throw away Textract results that were already paid for.
    record: dict = dict(existing) if existing else {"image": image_path.name}
    record["engines"] = dict(record.get("engines", {}))

    processed, elapsed, error = _timed(preprocess, str(image_path))
    # Only the shape - the cache is JSON and a numpy array is not serialisable.
    record["preprocess"] = {
        "seconds": round(elapsed, 4),
        "error": error,
        "shape": None if processed is None else list(processed.shape),
    }
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

    todo = [p for p in images if needs_run(cache.get(p.name), engines)]
    done = len(images) - len(todo)
    retries = sum(1 for p in todo if p.name in cache)

    summary = f"{len(images)} images, {done} already done, {len(todo)} to run"
    if retries:
        summary += f" ({retries} retrying after a previous failure)"
    print(summary)
    if args.mock:
        print("MOCK MODE - stub engines, results are not real")

    ran: list[str] = []
    for i, image_path in enumerate(todo, 1):
        print(f"  [{i}/{len(todo)}] {image_path.name}", flush=True)
        cache[image_path.name] = process_one(
            image_path, engines, args.mock, existing=cache.get(image_path.name)
        )
        ran.append(image_path.name)
        # Written every iteration so a crash or an interrupt doesn't lose paid calls.
        cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")

    print(f"\ncached {len(cache)} images to {cache_path}")

    # Report this run's failures separately from ones sitting in the cache from
    # earlier attempts, so a clean run doesn't look like a broken one.
    new_failures = engine_failures({n: cache[n] for n in ran})
    stale_failures = [f for f in engine_failures(cache) if f[0] not in ran]

    if new_failures:
        print(f"\n{len(new_failures)} engine failures in this run:")
        for name, engine, err in new_failures[:10]:
            print(f"  {name} [{engine}] {err}")
        if len(new_failures) > 10:
            print(f"  ... and {len(new_failures) - 10} more")
    elif ran:
        print(f"all {len(ran)} images processed cleanly")

    if stale_failures:
        print(
            f"\n{len(stale_failures)} failures still in the cache from earlier runs "
            f"(not retried because their engines weren't requested this time)"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
