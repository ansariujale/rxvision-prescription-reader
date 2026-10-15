"""Tests for which images the runner decides to (re)process.

The bug these guard against: a failed engine result was cached like a real one,
so `image in cache` counted as done. A transient problem - Tesseract not on
PATH, an expired AWS token - got baked in permanently, never retried, and
re-printed on every later run as if it had just happened.
"""

from eval.ocr_runner import engine_failures, needs_run

BOTH = {"tesseract", "textract"}


def ok(text="some text"):
    return {"text": text, "seconds": 1.0}


def failed(message="TesseractNotFoundError: nope"):
    return {"seconds": 0.1, "error": message}


def test_unseen_image_runs():
    assert needs_run(None, BOTH) is True


def test_fully_successful_image_is_skipped():
    record = {"engines": {"tesseract": ok(), "textract": ok()}}
    assert needs_run(record, BOTH) is False


def test_cached_failure_is_retried():
    """The regression. Previously this returned False and never re-ran."""
    record = {"engines": {"tesseract": failed(), "textract": ok()}}
    assert needs_run(record, BOTH) is True


def test_every_engine_failed_is_retried():
    record = {"engines": {"tesseract": failed(), "textract": failed()}}
    assert needs_run(record, BOTH) is True


def test_missing_engine_is_run():
    """Cached with Tesseract only, now Textract is wanted too."""
    record = {"engines": {"tesseract": ok()}}
    assert needs_run(record, BOTH) is True


def test_only_the_requested_engines_matter():
    """A Textract failure shouldn't force a re-run of a Tesseract-only pass."""
    record = {"engines": {"tesseract": ok(), "textract": failed()}}
    assert needs_run(record, {"tesseract"}) is False
    assert needs_run(record, {"textract"}) is True


def test_record_with_no_engines_at_all():
    assert needs_run({"image": "a.jpg"}, BOTH) is True


def test_engine_failures_lists_each_failure():
    cache = {
        "a.jpg": {"engines": {"tesseract": failed("boom"), "textract": ok()}},
        "b.jpg": {"engines": {"tesseract": ok(), "textract": ok()}},
        "c.jpg": {"engines": {"textract": failed("throttled")}},
    }
    failures = engine_failures(cache)
    assert sorted(f[0] for f in failures) == ["a.jpg", "c.jpg"]
    assert ("a.jpg", "tesseract", "boom") in failures


def test_engine_failures_empty_when_all_good():
    assert engine_failures({"a.jpg": {"engines": {"tesseract": ok()}}}) == []
