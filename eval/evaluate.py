"""Stage 2: score the cached OCR output against labels.

Free to run and offline, so sweep as much as you like. Every routing strategy
is derived from the same cache written by ocr_runner:

    tesseract-only   always use the Tesseract text
    textract-only    always use the Textract text
    escalate@T       use Tesseract when its confidence >= T, else Textract

Escalation at T=0 is Tesseract-only and at T=101 is Textract-only, so the sweep
brackets both baselines and shows exactly what the routing buys.

    python -m eval.evaluate --labels eval/labels.csv
    python -m eval.evaluate --labels eval/labels.csv --sweep
    python -m eval.evaluate --labels eval/labels.csv --match-threshold 72
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from eval.matching import load_medicine_names, match_medicines
from eval.metrics import Report, aggregate, score_image
from medicine_index import MedicineIndex, normalize, strip_dosage_form


def load_labels(path: Path) -> dict[str, list[str]]:
    """image,medicines with medicines pipe-separated. Empty means none legible."""
    labels: dict[str, list[str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            image = (row.get("image") or "").strip()
            if not image:
                continue
            raw = (row.get("medicines") or "").strip()
            labels[image] = [m.strip() for m in raw.split("|") if m.strip()]
    return labels


def text_for_mode(record: dict, mode: str, threshold: float) -> tuple[str | None, bool]:
    """Return (text, used_textract) for a routing mode, or (None, _) if unusable."""
    engines = record.get("engines", {})
    tess = engines.get("tesseract") or {}
    text = engines.get("textract") or {}

    tess_ok = not tess.get("error") and tess.get("text") is not None
    text_ok = not text.get("error") and text.get("text") is not None

    if mode == "tesseract":
        return (tess["text"], False) if tess_ok else (None, False)
    if mode == "textract":
        return (text["text"], True) if text_ok else (None, True)

    # escalation
    if tess_ok and tess.get("confidence", 0.0) >= threshold:
        return tess["text"], False
    if text_ok:
        return text["text"], True
    return (tess["text"], False) if tess_ok else (None, False)


def evaluate_mode(
    cache: dict,
    labels: dict[str, list[str]],
    matcher,
    mode: str,
    conf_threshold: float,
    match_threshold: int,
) -> tuple[Report, dict]:
    scores, escalations, skipped = [], 0, 0
    latency = []

    for image, truth in labels.items():
        record = cache.get(image)
        if record is None:
            skipped += 1
            continue

        text, used_textract = text_for_mode(record, mode, conf_threshold)
        if text is None:
            skipped += 1
            continue

        predicted = matcher(text, match_threshold)
        # The matcher reports dosage-form-stripped names ("augmentin 625 duo"),
        # so ground truth has to be reduced the same way or every comparison
        # fails on the word "Tablet" rather than on anything meaningful.
        expected = [strip_dosage_form(normalize(m)) for m in truth]
        scores.append(score_image(image, predicted, expected))

        escalations += 1 if used_textract else 0
        engine_key = "textract" if used_textract else "tesseract"
        latency.append(
            record.get("preprocess", {}).get("seconds", 0.0)
            + record.get("engines", {}).get(engine_key, {}).get("seconds", 0.0)
        )

    latency.sort()
    stats = {
        "textract_calls": escalations,
        "textract_call_rate": escalations / len(scores) if scores else 0.0,
        "skipped": skipped,
        "median_seconds": latency[len(latency) // 2] if latency else 0.0,
        "p95_seconds": latency[int(len(latency) * 0.95)] if latency else 0.0,
    }
    return aggregate(scores), stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="eval/labels.csv")
    parser.add_argument("--cache", default="eval/cache/ocr_results.json")
    parser.add_argument("--dataset", default="resource/medicine_names.csv")
    parser.add_argument("--match-threshold", type=int, default=68)
    parser.add_argument("--conf-threshold", type=float, default=70.0)
    parser.add_argument("--sweep", action="store_true", help="sweep the escalation threshold")
    parser.add_argument("--exact", action="store_true",
                        help="brute-force matching instead of the index; slow, for verifying the index")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    cache_path, labels_path = Path(args.cache), Path(args.labels)
    for p in (cache_path, labels_path):
        if not p.exists():
            print(f"missing: {p}")
            return 1

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    labels = load_labels(labels_path)
    print(f"{len(labels)} labelled images, {len(cache)} in OCR cache")

    if not Path(args.dataset).exists():
        print(f"missing medicine dataset: {args.dataset}")
        return 1
    if args.exact:
        # Brute force. Only here so the index can be checked against it.
        medicine_names = load_medicine_names(args.dataset)
        print(f"{len(medicine_names):,} names loaded - EXACT mode, brute force, expect minutes\n")

        def matcher(text, threshold):
            return match_medicines(text, medicine_names, threshold=threshold)
    else:
        index_cache = Path(args.dataset).with_suffix(".index.pkl")
        cached = index_cache.exists()
        t0 = time.perf_counter()
        index = MedicineIndex.from_csv(args.dataset, cache_path=index_cache)
        print(
            f"{len(index.keys):,} names, index "
            f"{'loaded from cache' if cached else 'built and cached'} "
            f"in {time.perf_counter() - t0:.1f}s\n"
        )

        def matcher(text, threshold):
            return index.match_all(text, threshold=threshold)

    header = f"{'mode':<22} {'n':>4}  {'prec':>6} {'recall':>7} {'f1':>6}  {'exact':>7}  {'textract':>8}"
    print(header)
    print("-" * len(header))

    results = {}
    modes = [
        ("tesseract-only", "tesseract", 0.0),
        ("textract-only", "textract", 0.0),
        (f"escalate@{args.conf_threshold:g}", "escalate", args.conf_threshold),
    ]
    for label, mode, conf in modes:
        report, stats = evaluate_mode(
            cache, labels, matcher, mode, conf, args.match_threshold
        )
        print(f"{report.as_row(label)}  {stats['textract_call_rate']:>7.1%}")
        results[label] = {"report": report.__dict__, "stats": stats}

    if args.sweep:
        print(f"\nescalation threshold sweep (match threshold {args.match_threshold})")
        print(header)
        print("-" * len(header))
        for conf in range(0, 101, 10):
            report, stats = evaluate_mode(
                cache, labels, matcher, "escalate", float(conf), args.match_threshold
            )
            print(f"{report.as_row(f'escalate@{conf}')}  {stats['textract_call_rate']:>7.1%}")
            results[f"escalate@{conf}"] = {"report": report.__dict__, "stats": stats}

    print(
        "\nprec/recall/f1 are micro-averaged. 'exact' is the share of prescriptions "
        "where the whole medicine set was right.\n'textract' is the share of images "
        "that cost an API call."
    )

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
