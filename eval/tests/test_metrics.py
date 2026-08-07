"""Tests for the scoring layer."""

from eval.metrics import aggregate, as_set, normalize, score_image


def test_normalize_matches_pipeline_rule():
    assert normalize("  Augmentin 625 Duo Tablet ") == "augmentin 625 duo tablet"
    assert normalize("Pantop 40mg") == "pantop 40"


def test_as_set_drops_blanks_and_dedupes():
    assert as_set(["Azithral 500", "", "  ", "azithral 500"]) == {"azithral 500"}


def test_perfect_prediction():
    s = score_image("a.jpg", ["Augmentin 625"], ["augmentin 625"])
    assert (s.true_positives, s.false_positives, s.false_negatives) == (1, 0, 0)
    assert s.exact_match
    assert s.precision == s.recall == s.f1 == 1.0


def test_missed_and_hallucinated():
    s = score_image("a.jpg", ["Pantop 40", "Crocin"], ["Pantop 40", "Azithral 500"])
    assert (s.true_positives, s.false_positives, s.false_negatives) == (1, 1, 1)
    assert s.precision == 0.5
    assert s.recall == 0.5
    assert not s.exact_match


def test_found_nothing_when_there_was_something():
    s = score_image("a.jpg", [], ["Azithral 500"])
    assert s.recall == 0.0
    assert s.precision == 0.0
    assert not s.exact_match


def test_correctly_found_nothing():
    """An illegible prescription with no readable medicines is a pass, not a fail."""
    s = score_image("a.jpg", [], [])
    assert s.exact_match
    assert s.precision == 1.0
    assert s.recall == 1.0


def test_hallucinated_on_an_empty_prescription():
    s = score_image("a.jpg", ["Crocin"], [])
    assert s.precision == 0.0
    assert s.recall == 0.0
    assert not s.exact_match


def test_case_and_mg_differences_do_not_count_as_errors():
    s = score_image("a.jpg", ["PANTOP 40mg"], ["pantop 40"])
    assert s.exact_match


def test_aggregate_micro_vs_macro_differ_with_uneven_lengths():
    """One long prescription done badly, one short one done perfectly.

    Micro pools all medicines so the long one dominates; macro weights the two
    images equally. The gap is the point of reporting both.
    """
    long_bad = score_image("long.jpg", ["a"], ["a", "b", "c", "d"])   # 1/4 recall
    short_good = score_image("short.jpg", ["z"], ["z"])               # 1/1 recall

    r = aggregate([long_bad, short_good])
    assert r.n == 2
    assert r.micro_recall == 2 / 5
    assert r.macro_recall == (0.25 + 1.0) / 2
    assert r.micro_recall != r.macro_recall
    assert r.exact_match_rate == 0.5


def test_aggregate_totals():
    r = aggregate([
        score_image("a.jpg", ["x", "y"], ["x"]),
        score_image("b.jpg", [], ["q"]),
    ])
    assert r.total_true_positives == 1
    assert r.total_false_positives == 1
    assert r.total_false_negatives == 1


def test_aggregate_of_nothing():
    r = aggregate([])
    assert r.n == 0
    assert r.micro_f1 == 0.0
