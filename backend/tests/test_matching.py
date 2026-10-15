from app.services.matching.index import MedicineIndex, clean_ocr_line, strip_dosage_form
from app.services.ocr.base import ExtractedMedicine, OcrResult
from app.services.ocr.mock import SAMPLE
from app.services.pipeline import Draft, dedupe, drafts_from_result


def test_strip_dosage_form_keeps_names_containing_form_words():
    assert strip_dosage_form("augmentin 625 duo tablet") == "augmentin 625 duo"
    assert strip_dosage_form("dolo 650 tablel") == "dolo 650"  # OCR damage
    assert strip_dosage_form("clopilet") == "clopilet"
    assert strip_dosage_form("ventab dxt") == "ventab dxt"


def test_clean_ocr_line():
    assert clean_ocr_line("1. scata 25") == "scata 25"
    assert clean_ocr_line("t. catel 40") == "catel 40"


def test_match_returns_catalogue_id(sample_index):
    hit = sample_index.match("Augrnentin 625 Duo")  # m misread as rn
    assert hit is not None
    assert hit.name == "Augmentin 625 Duo Tablet"
    assert hit.medicine_id == 1
    assert 68 <= hit.score <= 100


def test_short_lines_and_noise_do_not_match(sample_index):
    assert sample_index.match("x 10") is None
    assert sample_index.match("Dr. A. Mehta, MBBS MD") is None


def test_search_prefers_prefix(sample_index):
    names = [m.name for m in sample_index.search("augm", limit=3)]
    assert names and all(n.startswith("Augmentin") for n in names)


def test_save_and_load_round_trip(tmp_path, sample_index):
    path = tmp_path / "idx.pkl"
    sample_index.save(path)
    loaded = MedicineIndex.load(path)
    assert loaded.match("pan 40") == sample_index.match("pan 40")


def test_empty_index_matches_nothing():
    assert MedicineIndex([]).match("augmentin 625") is None


def test_text_provider_pipeline(sample_index):
    lines = SAMPLE.splitlines()
    drafts = drafts_from_result(OcrResult(SAMPLE, lines), sample_index, 68)
    names = [d.name for d in drafts]
    assert names == [
        "Augmentin 625 Duo Tablet",
        "Pan 40 Tablet",
        "Dolo 650 Tablet",
        "Ascoril LS Syrup",
        "Becosules Capsule",
    ]
    augmentin = drafts[0]
    assert (augmentin.frequency, augmentin.duration, augmentin.timing) == ("1-0-1", "5 days", "After food")
    assert drafts[3].strength == "10 ml" and drafts[3].frequency == "Three times daily"


def test_structured_provider_keeps_unmatched_and_uses_strength(sample_index):
    result = OcrResult(
        "...",
        [],
        medicines=[
            ExtractedMedicine(name="Azithral", strength="500 mg", frequency="OD", duration="3 days"),
            ExtractedMedicine(name="Zxqvorin", frequency="BD"),
        ],
    )
    first, second = drafts_from_result(result, sample_index, 68)
    assert first.name == "Azithral 500 Tablet"  # strength picked 500 over 250
    assert first.frequency == "Once daily"
    assert second.medicine_id is None and second.confidence is None
    assert second.name == "Zxqvorin" and second.frequency == "Twice daily"


def test_dedupe_keeps_more_confident():
    drafts = [
        Draft("A", 1, 0.7), Draft("B", None, None), Draft("A again", 1, 0.9), Draft("C", 2, 0.8)
    ]
    assert [d.name for d in dedupe(drafts)] == ["A again", "B", "C"]
