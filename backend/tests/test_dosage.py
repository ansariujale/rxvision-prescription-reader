import doctest

import pytest

from app.services import dosage
from app.services.dosage import normalise_frequency, parse_line


def test_doctests():
    assert doctest.testmod(dosage).failed == 0


@pytest.mark.parametrize(
    "line, name, strength, dose, frequency, duration, timing",
    [
        ("1. Tab Augmentin 625 Duo 1-0-1 x 5 days after food",
         "Augmentin 625 Duo", None, None, "1-0-1", "5 days", "After food"),
        ("2. Tab Pan 40 1-0-0 before breakfast x 7 days",
         "Pan 40", None, None, "1-0-0", "7 days", "Before food"),
        ("3. Tab Dolo 650 SOS for fever", "Dolo 650 for fever", None, None, "As needed", None, None),
        ("4. Syp Ascoril LS 10 ml TDS x 5d", "Ascoril LS", "10 ml", None, "Three times daily", "5 days", None),
        ("Cap Becosules 1-0-0 x 1 month", "Becosules", None, None, "1-0-0", "1 month", None),
        ("Tab. Azithral 500mg OD x3d", "Azithral", "500 mg", None, "Once daily", "3 days", None),
        ("D-Rise 60k once a week", "D-Rise", "60000 IU", None, "Once weekly", None, None),
        ("Tab Ultracet 1/2 tab BD", "Ultracet", None, "½ tablet", "Twice daily", None, None),
        ("Asthalin inhaler 2 puffs SOS", "Asthalin inhaler", None, "2 puffs", "As needed", None, None),
        ("Tab Nexito 10 0-0-1 at bedtime", "Nexito 10", None, None, "0-0-1", None, "At bedtime"),
        ("Pantop 40 empty stomach for 2 weeks", "Pantop 40", None, None, None, "2 weeks", "Empty stomach"),
    ],
)
def test_parse_line(line, name, strength, dose, frequency, duration, timing):
    p = parse_line(line)
    assert (p.name_part, p.strength, p.dose, p.frequency, p.duration, p.timing) == (
        name, strength, dose, frequency, duration, timing
    )


def test_half_pattern_frequency():
    assert parse_line("Tab Telma 40 1/2-0-1/2").frequency == "1/2-0-1/2"


def test_names_containing_form_words_survive():
    # "tab" inside "Ventab" and "cr" at the start of "Crocin" are not prefixes.
    assert parse_line("Ventab DXT 1-0-0").name_part == "Ventab DXT"
    assert parse_line("Crocin Advance 1-1-1").name_part == "Crocin Advance"


@pytest.mark.parametrize(
    "raw, expected",
    [("BD", "Twice daily"), ("1 - 0 - 1", "1-0-1"), ("tds", "Three times daily"),
     ("at night", "At bedtime"), (None, None), ("every other day", "every other day")],
)
def test_normalise_frequency(raw, expected):
    assert normalise_frequency(raw) == expected
