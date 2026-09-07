"""
Tests for client-side range post-filter in get_historical_ohlcv.

The filter runs after all WebSocket bars are collected and removes any bars
whose timestamp falls outside [from_ts, end_of_day_timestamp(end)].

No real network calls — all external I/O is mocked.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.chart.utils import end_of_day_timestamp, to_unix_timestamp

SYMBOL: str = "NASDAQ:AAPL"

# ── Timestamps used in tests ────────────────────────────────────────────────
# 2025-01-01 00:00:00 UTC
TS_2025_JAN_01: int = to_unix_timestamp("2025-01-01")
# 2025-12-31 00:00:00 UTC  (midnight, what daily bar stamp would be)
TS_2025_DEC_31: int = to_unix_timestamp("2025-12-31")
# 2025-12-31 16:00:00 UTC  (intraday bar on last day)
TS_2025_DEC_31_16H: int = TS_2025_DEC_31 + 16 * 3600
# 2026-01-01 00:00:00 UTC  (out-of-range — future year)
TS_2026_JAN_01: int = to_unix_timestamp("2026-01-01")
# 2024-12-31 00:00:00 UTC  (out-of-range — before start)
TS_2024_DEC_31: int = to_unix_timestamp("2024-12-31")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_bar(ts: int) -> dict[str, Any]:
    """Build a single bar entry in TradingView timescale_update format."""
    return {"i": 0, "v": [float(ts), 100.0, 105.0, 95.0, 102.0, 1000.0]}


def _make_timescale_update(timestamps: list[int]) -> dict[str, Any]:
    """Build a fake timescale_update message for the given timestamps."""
    series: list[dict[str, Any]] = [_make_bar(ts) for ts in timestamps]
    return {"m": "timescale_update", "p": ["cs_xxx", {"sds_1": {"s": series}}]}


_SERIES_COMPLETED: dict[str, Any] = {
    "m": "series_completed",
    "p": ["cs_xxx", "sds_1", "sds_sym_1", "ok"],
}


async def _fake_stream(
    messages: list[dict[str, Any]],
) -> AsyncGenerator[dict[str, Any], None]:
    for msg in messages:
        yield msg


def _make_range_client(messages: list[dict[str, Any]]) -> OHLCV:
    """Return an OHLCV client wired to a fake stream, bypassing WebSocket."""
    client: OHLCV = OHLCV()
    client._prepare_chart_session = AsyncMock()  # type: ignore[method-assign]
    client.connection_service = MagicMock()
    client.connection_service.get_data_stream = lambda: _fake_stream(messages)
    client.connection_service.close = AsyncMock()
    return client


# ── end_of_day_timestamp unit tests ──────────────────────────────────────────


class TestEndOfDayTimestamp:
    """Unit tests for the end_of_day_timestamp helper."""

    def test_date_only_string_adds_86399(self) -> None:
        base: int = to_unix_timestamp("2025-12-31")
        assert end_of_day_timestamp("2025-12-31") == base + 86399

    def test_datetime_string_with_space_is_unchanged(self) -> None:
        ts: int = to_unix_timestamp("2025-12-31 16:00")
        assert end_of_day_timestamp("2025-12-31 16:00") == ts

    def test_datetime_string_with_T_is_unchanged(self) -> None:
        ts: int = to_unix_timestamp("2025-12-31T16:00:00")
        assert end_of_day_timestamp("2025-12-31T16:00:00") == ts

    def test_midnight_datetime_object_is_exact(self) -> None:
        """A midnight datetime carries an explicit time, so it is NOT date-only.

        Only date-only *strings* (no ``" "`` / ``"T"``) mean "whole day".  A
        ``datetime(..., 0, 0, 0)`` is an exact midnight boundary and must not be
        expanded to end-of-day — otherwise a range ending at midnight would leak
        the following day's bars into the result.
        """
        dt: datetime = datetime(2025, 12, 31, 0, 0, 0, tzinfo=UTC)
        base: int = to_unix_timestamp(dt)
        assert end_of_day_timestamp(dt) == base

    def test_midnight_naive_datetime_object_is_exact(self) -> None:
        """A naive midnight datetime is assigned UTC and stays exact — no +86399."""
        dt: datetime = datetime(2025, 12, 31, 0, 0, 0)
        assert end_of_day_timestamp(dt) == to_unix_timestamp(dt)

    def test_iso_string_at_midnight_with_T_is_exact(self) -> None:
        """A string carrying an explicit midnight time is not date-only."""
        assert end_of_day_timestamp("2025-12-31T00:00:00Z") == to_unix_timestamp("2025-12-31")

    def test_datetime_object_with_time_is_unchanged(self) -> None:
        dt: datetime = datetime(2025, 12, 31, 16, 0, 0, tzinfo=UTC)
        base: int = to_unix_timestamp(dt)
        assert end_of_day_timestamp(dt) == base


# ── Integration tests: client-side post-filter ───────────────────────────────


class TestRangePostFilter:
    """
    Verify that get_historical_ohlcv removes bars outside [start, end] in range mode.
    All WebSocket I/O is mocked — tests exercise the post-filter logic only.
    """

    @pytest.mark.asyncio
    async def test_filter_removes_future_bars(self) -> None:
        """Bars from 2026 are removed when range is 2025-01-01 to 2025-12-31."""
        messages: list[dict[str, Any]] = [
            _SERIES_COMPLETED,  # First: create_series response — bars discarded
            _make_timescale_update([TS_2025_JAN_01, TS_2025_DEC_31, TS_2026_JAN_01]),
            _SERIES_COMPLETED,  # Second: modify_series response — break
        ]
        client: OHLCV = _make_range_client(messages)

        bars = await client.get_historical_ohlcv(
            exchange_symbol=SYMBOL,
            start="2025-01-01",
            end="2025-12-31",
        )

        timestamps: list[int] = [bar.timestamp for bar in bars]
        assert TS_2026_JAN_01 not in timestamps
        assert TS_2025_JAN_01 in timestamps
        assert TS_2025_DEC_31 in timestamps

    @pytest.mark.asyncio
    async def test_filter_removes_past_bars(self) -> None:
        """Bars from before start date are removed."""
        messages: list[dict[str, Any]] = [
            _SERIES_COMPLETED,  # First: create_series response — bars discarded
            _make_timescale_update([TS_2024_DEC_31, TS_2025_JAN_01, TS_2025_DEC_31]),
            _SERIES_COMPLETED,  # Second: modify_series response — break
        ]
        client: OHLCV = _make_range_client(messages)

        bars = await client.get_historical_ohlcv(
            exchange_symbol=SYMBOL,
            start="2025-01-01",
            end="2025-12-31",
        )

        timestamps: list[int] = [bar.timestamp for bar in bars]
        assert TS_2024_DEC_31 not in timestamps
        assert TS_2025_JAN_01 in timestamps

    @pytest.mark.asyncio
    async def test_filter_includes_boundary_bars(self) -> None:
        """Bars at exactly start and end-of-day boundaries are kept."""
        eod_ts: int = end_of_day_timestamp("2025-12-31")
        messages: list[dict[str, Any]] = [
            _SERIES_COMPLETED,  # First: create_series response — bars discarded
            _make_timescale_update([TS_2025_JAN_01, eod_ts]),
            _SERIES_COMPLETED,  # Second: modify_series response — break
        ]
        client: OHLCV = _make_range_client(messages)

        bars = await client.get_historical_ohlcv(
            exchange_symbol=SYMBOL,
            start="2025-01-01",
            end="2025-12-31",
        )

        timestamps: list[int] = [bar.timestamp for bar in bars]
        assert TS_2025_JAN_01 in timestamps
        assert eod_ts in timestamps

    @pytest.mark.asyncio
    async def test_intraday_bars_on_end_day_are_kept(self) -> None:
        """Intraday bars on the last calendar day are included when end is date-only."""
        messages: list[dict[str, Any]] = [
            _SERIES_COMPLETED,  # First: create_series response — bars discarded
            _make_timescale_update([TS_2025_JAN_01, TS_2025_DEC_31, TS_2025_DEC_31_16H]),
            _SERIES_COMPLETED,  # Second: modify_series response — break
        ]
        client: OHLCV = _make_range_client(messages)

        bars = await client.get_historical_ohlcv(
            exchange_symbol=SYMBOL,
            start="2025-01-01",
            end="2025-12-31",
        )

        timestamps: list[int] = [bar.timestamp for bar in bars]
        # Both midnight and 16:00 bars on Dec 31 should be kept
        assert TS_2025_DEC_31 in timestamps
        assert TS_2025_DEC_31_16H in timestamps

    @pytest.mark.asyncio
    async def test_explicit_end_time_bars_after_are_excluded(self) -> None:
        """When end includes a time component, bars after that exact time are excluded."""
        end_str: str = "2025-12-31 12:00"
        end_ts: int = to_unix_timestamp(end_str)

        messages: list[dict[str, Any]] = [
            _SERIES_COMPLETED,  # First: create_series response — bars discarded
            _make_timescale_update([TS_2025_JAN_01, end_ts, TS_2025_DEC_31_16H]),
            _SERIES_COMPLETED,  # Second: modify_series response — break
        ]
        client: OHLCV = _make_range_client(messages)

        bars = await client.get_historical_ohlcv(
            exchange_symbol=SYMBOL,
            start="2025-01-01",
            end=end_str,
        )

        timestamps: list[int] = [bar.timestamp for bar in bars]
        assert end_ts in timestamps
        # 16:00 bar is after 12:00 end — should be excluded
        assert TS_2025_DEC_31_16H not in timestamps

    @pytest.mark.asyncio
    async def test_count_mode_not_filtered(self) -> None:
        """Count mode bars are never range-filtered, even if timestamps vary widely."""
        messages: list[dict[str, Any]] = [
            _make_timescale_update([TS_2024_DEC_31, TS_2025_JAN_01, TS_2026_JAN_01]),
            _SERIES_COMPLETED,
        ]
        client: OHLCV = _make_range_client(messages)

        bars = await client.get_historical_ohlcv(
            exchange_symbol=SYMBOL,
            bars_count=3,
        )

        # All 3 bars must be present — no post-filter in count mode
        assert len(bars) == 3

    @pytest.mark.asyncio
    async def test_date_only_end_expands_range_param_and_keeps_last_day(self) -> None:
        """A date-only end expands to end-of-day in the server range and post-filter.

        The range_param sent to TradingView must end at 23:59:59 (midnight + 86399)
        for a date-only end, and an intraday bar on the final day must survive.
        """
        messages: list[dict[str, Any]] = [
            _SERIES_COMPLETED,
            _make_timescale_update([TS_2025_JAN_01, TS_2025_DEC_31, TS_2025_DEC_31_16H]),
            _SERIES_COMPLETED,
        ]
        client: OHLCV = _make_range_client(messages)

        bars = await client.get_historical_ohlcv(
            exchange_symbol=SYMBOL,
            start="2025-01-01",
            end="2025-12-31",
        )

        prepare_mock = client._prepare_chart_session
        assert prepare_mock.call_args is not None
        range_param: str = prepare_mock.call_args.kwargs["range_param"]
        to_ts = int(range_param[2:].split(":")[1])
        assert to_ts == TS_2025_DEC_31 + 86399

        timestamps: list[int] = [bar.timestamp for bar in bars]
        assert TS_2025_DEC_31 in timestamps
        assert TS_2025_DEC_31_16H in timestamps

    @pytest.mark.asyncio
    async def test_exact_midnight_datetime_end_does_not_leak_following_day(self) -> None:
        """A datetime end at exact midnight does not leak the following day's bars.

        A datetime(..., 0, 0, 0) end is an exact boundary — not "the whole day" — so
        bars after that midnight must be excluded from both the create_series
        fallback and the post-filter.
        """
        end: datetime = datetime(2025, 12, 31, 0, 0, 0, tzinfo=UTC)
        messages: list[dict[str, Any]] = [
            _make_timescale_update([TS_2025_JAN_01, TS_2025_DEC_31, TS_2025_DEC_31_16H]),
            _SERIES_COMPLETED,  # single event → create_series fallback path
        ]
        client: OHLCV = _make_range_client(messages)

        bars = await client.get_historical_ohlcv(
            exchange_symbol=SYMBOL,
            start="2025-01-01",
            end=end,
        )

        timestamps: list[int] = [bar.timestamp for bar in bars]
        assert TS_2025_JAN_01 in timestamps
        assert TS_2025_DEC_31 in timestamps  # exact midnight is inclusive
        assert TS_2025_DEC_31_16H not in timestamps  # following day must not leak
