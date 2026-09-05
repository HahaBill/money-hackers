import pytest

from rcg.validator import ValidationError, extract_numbers, validate_text


def test_extracts_signed_integers_but_not_period_identifier():
    assert extract_numbers("2026-08 profit changed -$4,820 and volume +11%") == [-4820.0, 11.0]


def test_rejects_nearby_but_unsourced_percentage():
    with pytest.raises(ValidationError):
        validate_text("Revenue rose 20%.", {"change_pct": 11.2, "small_dollars": 0.0})


def test_allows_rounded_sourced_currency():
    validate_text("Profit fell about $4,800.", {"profit_delta": -4820.0})
