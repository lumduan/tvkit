"""Tests for scanner row-drop reporting.

``ScannerResponse.from_api_response`` skips rows it cannot parse so that one bad record
cannot discard a whole response. It used to do so behind a bare ``except Exception:
continue`` with no logging, which made ``len(data) < total_count`` ambiguous — it could
mean either "the requested range was smaller" or "we threw your data away". Every drop is
now counted on ``dropped_row_count`` and logged at WARNING.
"""

import logging
from typing import Any

import pytest

from tvkit.api.scanner.models.scanner import ScannerResponse

COLUMNS: list[str] = ["name", "close", "volume"]

GOOD_ROW: dict[str, Any] = {"s": "NASDAQ:AAPL", "d": ["AAPL", 305.59, 38169263]}
BAD_VALUE_ROW: dict[str, Any] = {"s": "NASDAQ:MSFT", "d": ["MSFT", "not-a-number", 22118613]}
SHORT_ROW: dict[str, Any] = {"s": "NASDAQ:NVDA", "d": ["NVDA", 225.01]}


def test_clean_response_reports_no_drops() -> None:
    """A fully parseable payload leaves dropped_row_count at zero."""
    response: dict[str, Any] = {"data": [GOOD_ROW], "totalCount": 1}

    parsed = ScannerResponse.from_api_response(response, COLUMNS)

    assert len(parsed.data) == 1
    assert parsed.dropped_row_count == 0


def test_clean_response_logs_nothing() -> None:
    """No warning is emitted when nothing is discarded."""
    response: dict[str, Any] = {"data": [GOOD_ROW], "totalCount": 1}

    logger = logging.getLogger("tvkit.api.scanner.models.scanner")
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append  # type: ignore[method-assign]
    logger.addHandler(handler)
    try:
        ScannerResponse.from_api_response(response, COLUMNS)
    finally:
        logger.removeHandler(handler)

    assert records == []


def test_unparseable_rows_are_counted_not_hidden() -> None:
    """Rows that fail validation are skipped but reported via dropped_row_count."""
    response: dict[str, Any] = {
        "data": [GOOD_ROW, BAD_VALUE_ROW, SHORT_ROW],
        "totalCount": 3,
    }

    parsed = ScannerResponse.from_api_response(response, COLUMNS)

    assert [s.name for s in parsed.data] == ["AAPL"]
    assert parsed.dropped_row_count == 2, "silent data loss — the drop was not reported"
    # The shortfall is now explainable: 3 rows in, 1 out, 2 accounted for.
    assert len(parsed.data) + parsed.dropped_row_count == len(response["data"])


def test_dropped_row_count_survives_serialization() -> None:
    """The count is a real field, so a pipeline can assert on a dumped response."""
    response: dict[str, Any] = {"data": [GOOD_ROW, SHORT_ROW], "totalCount": 2}

    dumped = ScannerResponse.from_api_response(response, COLUMNS).model_dump()

    assert dumped["dropped_row_count"] == 1


def test_each_drop_is_logged_with_index_and_symbol(caplog: pytest.LogCaptureFixture) -> None:
    """Each discarded row is logged at WARNING, naming the row and the symbol."""
    response: dict[str, Any] = {
        "data": [GOOD_ROW, BAD_VALUE_ROW, SHORT_ROW],
        "totalCount": 3,
    }

    with caplog.at_level(logging.WARNING, logger="tvkit.api.scanner.models.scanner"):
        ScannerResponse.from_api_response(response, COLUMNS)

    per_row = [r for r in caplog.records if getattr(r, "row_index", None) is not None]
    assert len(per_row) == 2
    assert {r.row_index for r in per_row} == {1, 2}  # type: ignore[attr-defined]
    assert {r.symbol for r in per_row} == {"NASDAQ:MSFT", "NASDAQ:NVDA"}  # type: ignore[attr-defined]

    summary = [r for r in caplog.records if getattr(r, "dropped_row_count", None) is not None]
    assert len(summary) == 1
    assert summary[0].dropped_row_count == 2  # type: ignore[attr-defined]


def test_caller_errors_are_no_longer_swallowed() -> None:
    """A bug in the call — not in the payload — must surface, not vanish.

    The previous bare ``except Exception`` turned this into an empty response.
    """
    response: dict[str, Any] = {"data": [GOOD_ROW], "totalCount": 1}

    with pytest.raises(TypeError):
        ScannerResponse.from_api_response(response, None)  # type: ignore[arg-type]


def test_missing_data_key_yields_an_empty_response() -> None:
    """A payload with no 'data' key is empty, not a drop."""
    parsed = ScannerResponse.from_api_response({"totalCount": 0}, COLUMNS)

    assert parsed.data == []
    assert parsed.dropped_row_count == 0
