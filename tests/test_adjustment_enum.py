"""Unit tests for the Adjustment enum contract."""

import pytest

from tvkit.api.chart import Adjustment
from tvkit.api.chart.models.adjustment import Adjustment as AdjDirect


def test_adjustment_importable_from_chart_package() -> None:
    """Adjustment is accessible from the public tvkit.api.chart surface."""
    assert Adjustment.SPLITS


def test_adjustment_splits_value() -> None:
    """SPLITS.value must equal the TradingView protocol string 'splits'."""
    assert Adjustment.SPLITS.value == "splits"


def test_adjustment_dividends_value() -> None:
    """DIVIDENDS.value must equal the TradingView protocol string 'dividends'."""
    assert Adjustment.DIVIDENDS.value == "dividends"


def test_adjustment_is_str_enum() -> None:
    """Adjustment members must be str instances for direct JSON embedding."""
    assert isinstance(Adjustment.SPLITS, str)
    assert isinstance(Adjustment.DIVIDENDS, str)


def test_adjustment_coercion_splits() -> None:
    """Adjustment('splits') must coerce to Adjustment.SPLITS."""
    assert Adjustment("splits") == Adjustment.SPLITS


def test_adjustment_coercion_dividends() -> None:
    """Adjustment('dividends') must coerce to Adjustment.DIVIDENDS."""
    assert Adjustment("dividends") == Adjustment.DIVIDENDS


def test_adjustment_coercion_invalid_string_raises_value_error() -> None:
    """Unknown adjustment strings must raise ValueError."""
    with pytest.raises(ValueError):
        Adjustment("none")


def test_adjustment_coercion_empty_string_raises_value_error() -> None:
    """Empty string must raise ValueError."""
    with pytest.raises(ValueError):
        Adjustment("")


def test_adjustment_direct_import_matches_package_import() -> None:
    """Direct module import and package-level import must resolve to the same class."""
    assert Adjustment.SPLITS is AdjDirect.SPLITS
    assert Adjustment.DIVIDENDS is AdjDirect.DIVIDENDS


def test_adjustment_str_equality() -> None:
    """As a str enum, Adjustment.SPLITS == 'splits' must hold."""
    assert Adjustment.SPLITS == "splits"
    assert Adjustment.DIVIDENDS == "dividends"


@pytest.mark.parametrize("adj", [Adjustment.SPLITS, Adjustment.DIVIDENDS])
def test_adjustment_value_is_json_serializable(adj: Adjustment) -> None:
    """Each member's .value must be usable directly in json.dumps contexts."""
    import json

    payload = json.dumps({"adjustment": adj.value})
    assert adj.value in payload
