"""M0 · Your first test-driven module: money as integer cents.   make check M=00"""

import pytest

from tinyshop.money import format_eur, split_evenly, to_cents


@pytest.mark.parametrize(
    ("text", "cents"),
    [("19.99", 1999), ("19,99", 1999), ("5", 500), ("0.5", 50), ("0.05", 5), (" 7.10 ", 710), ("0", 0)],
)
def test_to_cents(text, cents):
    assert to_cents(text) == cents


@pytest.mark.parametrize("bad", ["", "abc", "1.999", "-5", "1.2.3", "€5"])
def test_to_cents_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        to_cents(bad)


def test_float_trap_is_avoided():
    # 0.1 + 0.2 != 0.3 with floats; with cents it is exact
    assert to_cents("0.10") + to_cents("0.20") == to_cents("0.30")


def test_format_eur():
    assert format_eur(1999) == "19.99 EUR"
    assert format_eur(5) == "0.05 EUR"
    assert format_eur(0) == "0.00 EUR"
    with pytest.raises(ValueError):
        format_eur(-1)


def test_split_evenly_never_loses_a_cent():
    assert split_evenly(1000, 3) == [334, 333, 333]
    assert split_evenly(10, 5) == [2, 2, 2, 2, 2]
    assert sum(split_evenly(9999, 7)) == 9999
    with pytest.raises(ValueError):
        split_evenly(100, 0)
