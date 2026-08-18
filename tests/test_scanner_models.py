"""Regression tests for scanner row parsing.

TradingView returns ``market_cap_basic`` as a fractional float (e.g.
``5445242088563.96``). While the field was annotated ``int | None`` every such row
failed validation and was silently discarded by
:meth:`ScannerResponse.from_api_response`, so any query selecting that column came
back with zero rows despite a non-zero ``totalCount``.
"""

from typing import Any

from tvkit.api.scanner.models.scanner import ScannerResponse, StockData

# Shape of a real scanner response for NASDAQ:NVDA (market_cap_basic is fractional).
COLUMNS: list[str] = ["name", "close", "volume", "market_cap_basic"]
ROW: list[Any] = ["NVDA", 225.01, 93675880, 5445242088563.96]


def test_fractional_market_cap_is_accepted() -> None:
    """A fractional market cap must validate rather than raise."""
    stock = StockData(name="NVDA", market_cap_basic=5445242088563.96)
    assert stock.market_cap_basic == 5445242088563.96


def test_from_scanner_row_parses_fractional_market_cap() -> None:
    """Row-level parsing must survive a fractional market cap."""
    stock = StockData.from_scanner_row(ROW, COLUMNS)
    assert stock.name == "NVDA"
    assert stock.close == 225.01
    assert stock.market_cap_basic == 5445242088563.96


def test_from_api_response_does_not_drop_fractional_rows() -> None:
    """The user-visible symptom: rows must not vanish from the parsed response."""
    response: dict[str, Any] = {
        "data": [{"s": "NASDAQ:NVDA", "d": ROW}],
        "totalCount": 4943,
    }

    parsed = ScannerResponse.from_api_response(response, COLUMNS)

    assert parsed.total_count == 4943
    assert len(parsed.data) == 1, "fractional market_cap_basic row was silently dropped"
    assert parsed.data[0].name == "NVDA"
