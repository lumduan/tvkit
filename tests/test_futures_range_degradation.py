"""
Tests for the continuous futures intraday range degradation bug fix (v0.11.1).

Covers three independent fixes:

  Fix 1 — pre_modify_bars_in_range fallback in _fetch_single_range():
    When TradingView sends only one series_completed event (throttled server or
    single-event protocol variant), bars from the create_series response that fall
    within the requested date range are used as a fallback instead of raising
    NoHistoricalDataError.

  Fix 2 — inter_segment_delay in SegmentedFetchService:
    asyncio.sleep() is injected between consecutive segment fetches when
    inter_segment_delay > 0.0. The sleep is skipped after the last segment.

  Fix 3 — segment_delay public parameter on get_historical_ohlcv():
    The new keyword-only segment_delay parameter is forwarded to
    SegmentedFetchService when the range triggers segmentation.
    Ignored in count mode and for single-segment ranges.

No live WebSocket connections — all external I/O is mocked.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from tvkit.api.chart.exceptions import NoHistoricalDataError
from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.chart.ohlcv import OHLCV, _StreamingSession
from tvkit.api.chart.services.segmented_fetch_service import SegmentedFetchService
from tvkit.api.chart.utils import MAX_BARS_REQUEST

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

SYMBOL: str = "CME_MINI:MNQ1!"

# Unix timestamp for 2024-01-01 00:00:00 UTC — bars stamped here are inside
# the 2024-01-01 → 2024-12-31 test window used throughout this module.
_TS_JAN_2024: float = 1_704_067_200.0

# A timestamp clearly OUTSIDE the 2024 test window (year 2023).
_TS_OUTSIDE_RANGE: float = 1_672_531_200.0  # 2023-01-01 00:00 UTC

# ---------------------------------------------------------------------------
# Wire messages
# ---------------------------------------------------------------------------

SERIES_COMPLETED_MSG: dict[str, Any] = {
    "m": "series_completed",
    "p": ["cs_xxx", "sds_1", "sds_sym_1", "ok"],
}
SERIES_LOADING_MSG: dict[str, Any] = {
    "m": "series_loading",
    "p": ["cs_xxx", "sds_1"],
}


def make_timescale_update(
    bars_count: int,
    base_ts: float = _TS_JAN_2024,
) -> dict[str, Any]:
    """Build a fake timescale_update with ``bars_count`` bars starting at ``base_ts``."""
    series: list[dict[str, Any]] = [
        {"i": i, "v": [base_ts + i * 60, 100.0, 105.0, 95.0, 102.0, float(i + 1)]}
        for i in range(bars_count)
    ]
    return {"m": "timescale_update", "p": ["cs_xxx", {"sds_1": {"s": series}}]}


async def fake_stream(
    messages: list[dict[str, Any]],
) -> AsyncGenerator[dict[str, Any], None]:
    """Yield a pre-defined sequence of messages then stop."""
    for msg in messages:
        yield msg


def _make_range_client(messages: list[dict[str, Any]]) -> OHLCV:
    """Return an OHLCV client wired for range-mode tests with mocked services."""
    client = OHLCV()
    client._prepare_chart_session = AsyncMock()  # type: ignore[method-assign]
    client._session = _StreamingSession(  # type: ignore[assignment]
        symbol=SYMBOL,
        interval="1",
        bars_count=MAX_BARS_REQUEST,
        quote_session="qs_test",
        chart_session="cs_test",
    )
    client.connection_service = MagicMock()
    client.connection_service.get_data_stream = lambda: fake_stream(messages)
    client.connection_service.close = AsyncMock()
    client.message_service = MagicMock()  # type: ignore[assignment]
    return client


def _make_patches() -> dict[str, Any]:
    return {
        "validate_symbols": AsyncMock(return_value=True),
        "normalize_symbol": MagicMock(return_value=SYMBOL),
        "validate_interval": MagicMock(),
    }


def make_bar(ts: float, volume: float = 100.0) -> OHLCVBar:
    return OHLCVBar(timestamp=ts, open=1.0, high=2.0, low=0.5, close=1.5, volume=volume)


# ===========================================================================
# Fix 1 — pre_modify_bars_in_range fallback
# ===========================================================================


class TestPreModifyFallback:
    """
    Fix 1: fallback for single-event series_completed in _fetch_single_range().

    When TradingView sends only the first series_completed (throttle, continuous
    futures edge case, or single-event protocol variant), bars from the
    create_series response that fall within the requested date range are saved as
    a fallback. If modify_series returns nothing, those bars are returned instead
    of raising NoHistoricalDataError.
    """

    @pytest.mark.asyncio
    async def test_single_event_activates_fallback(self) -> None:
        """Single series_completed with in-range bars → fallback returns those bars.

        Simulates TradingView throttling on CME_MINI:MNQ1!: bars arrive before
        the first (and only) series_completed. The stream then ends with no second
        event. Expected: fallback activates and returns the in-range bars.
        """
        messages: list[dict[str, Any]] = [
            SERIES_LOADING_MSG,
            make_timescale_update(bars_count=5, base_ts=_TS_JAN_2024),
            SERIES_COMPLETED_MSG,  # Only one event — throttled server
        ]
        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            result = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2024-01-01", end="2024-12-31"
            )

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_single_event_no_in_range_bars_raises(self) -> None:
        """Single series_completed with NO in-range bars → NoHistoricalDataError.

        The create_series response contains only bars outside the requested range.
        Fallback cannot activate, so NoHistoricalDataError is raised.

        Uses a same-day range (start == end) so _needs_segmentation() returns False
        and the single-range path in _fetch_single_range() is exercised directly.
        """
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5, base_ts=_TS_OUTSIDE_RANGE),
            SERIES_COMPLETED_MSG,
        ]
        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            with pytest.raises(NoHistoricalDataError):
                # Same-day range → 0 estimated bars → no segmentation
                await client.get_historical_ohlcv(SYMBOL, "1", start="2024-01-01", end="2024-01-01")

    @pytest.mark.asyncio
    async def test_single_event_fallback_filters_out_of_range_bars(self) -> None:
        """Fallback only returns bars that fall within the requested date range.

        The create_series response contains both in-range and out-of-range bars.
        Only the in-range subset must be returned via the fallback.
        """
        in_range_ts = _TS_JAN_2024
        out_of_range_ts = _TS_OUTSIDE_RANGE
        series: list[dict[str, Any]] = [
            {"i": i, "v": [out_of_range_ts + i * 60, 1.0, 2.0, 0.5, 1.5, 1.0]} for i in range(3)
        ] + [{"i": i + 3, "v": [in_range_ts + i * 60, 1.0, 2.0, 0.5, 1.5, 1.0]} for i in range(4)]
        msg: dict[str, Any] = {"m": "timescale_update", "p": ["cs_xxx", {"sds_1": {"s": series}}]}
        messages = [msg, SERIES_COMPLETED_MSG]

        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            result = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2024-01-01", end="2024-12-31"
            )

        assert len(result) == 4
        assert all(b.timestamp >= _TS_JAN_2024 for b in result)

    @pytest.mark.asyncio
    async def test_two_events_normal_path_not_affected(self) -> None:
        """Two series_completed events — normal path: fallback is NOT activated.

        The second series_completed carries the modify_series response with bars.
        The first-event create_series bars are discarded as usual.
        """
        create_series_bars = make_timescale_update(bars_count=3, base_ts=_TS_JAN_2024)
        modify_series_bars = make_timescale_update(bars_count=7, base_ts=_TS_JAN_2024 + 10_000)
        messages: list[dict[str, Any]] = [
            create_series_bars,
            SERIES_COMPLETED_MSG,  # First: create_series — cleared
            modify_series_bars,
            SERIES_COMPLETED_MSG,  # Second: modify_series — break
        ]
        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            result = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2024-01-01", end="2024-12-31"
            )

        # Only the 7 modify_series bars, not the 3 create_series bars
        assert len(result) == 7
        assert all(b.timestamp >= _TS_JAN_2024 + 10_000 for b in result)

    @pytest.mark.asyncio
    async def test_two_events_second_empty_activates_fallback(self) -> None:
        """Two events but second event returns no bars — fallback activates.

        The modify_series response delivers zero bars (server throttle at its worst).
        The saved create_series bars are returned via the fallback.
        """
        create_series_bars = make_timescale_update(bars_count=5, base_ts=_TS_JAN_2024)
        messages: list[dict[str, Any]] = [
            create_series_bars,
            SERIES_COMPLETED_MSG,  # First: create_series — cleared, fallback saved
            SERIES_COMPLETED_MSG,  # Second: modify_series — no bars, break
        ]
        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            result = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2024-01-01", end="2024-12-31"
            )

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_fallback_bars_sorted_ascending(self) -> None:
        """Fallback bars are sorted in ascending timestamp order."""
        base = _TS_JAN_2024
        series: list[dict[str, Any]] = [
            {"i": i, "v": [base + (4 - i) * 60, 1.0, 2.0, 0.5, 1.5, 1.0]}  # descending ts
            for i in range(5)
        ]
        msg: dict[str, Any] = {"m": "timescale_update", "p": ["cs_xxx", {"sds_1": {"s": series}}]}
        messages = [msg, SERIES_COMPLETED_MSG]

        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            result = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2024-01-01", end="2024-12-31"
            )

        timestamps = [b.timestamp for b in result]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_fallback_log_message_emitted(self, caplog: pytest.LogCaptureFixture) -> None:
        """A structured INFO log is emitted when the fallback activates."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=3, base_ts=_TS_JAN_2024),
            SERIES_COMPLETED_MSG,
        ]
        client = _make_range_client(messages)

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()),
            caplog.at_level(logging.INFO, logger="tvkit.api.chart.ohlcv"),
        ):
            await client.get_historical_ohlcv(SYMBOL, "1", start="2024-01-01", end="2024-12-31")

        fallback_records = [r for r in caplog.records if "falling back" in r.message]
        assert len(fallback_records) == 1
        assert "3" in fallback_records[0].message

    @pytest.mark.asyncio
    async def test_fallback_not_triggered_when_modify_series_has_bars(self) -> None:
        """The fallback bar count is irrelevant when modify_series provides bars.

        Even if the create_series response had more in-range bars than the
        modify_series response, the latter always wins (normal path).
        """
        create_series_bars = make_timescale_update(bars_count=10, base_ts=_TS_JAN_2024)
        modify_series_bars = make_timescale_update(bars_count=2, base_ts=_TS_JAN_2024 + 50_000)
        messages: list[dict[str, Any]] = [
            create_series_bars,
            SERIES_COMPLETED_MSG,
            modify_series_bars,
            SERIES_COMPLETED_MSG,
        ]
        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            result = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2024-01-01", end="2024-12-31"
            )

        assert len(result) == 2
        assert all(b.timestamp >= _TS_JAN_2024 + 50_000 for b in result)

    @pytest.mark.asyncio
    async def test_empty_create_series_single_event_raises(self) -> None:
        """No bars before the only series_completed → NoHistoricalDataError.

        Uses a same-day range (start == end) so _needs_segmentation() returns False
        and the single-range path in _fetch_single_range() is exercised directly.
        """
        messages: list[dict[str, Any]] = [
            SERIES_LOADING_MSG,
            SERIES_COMPLETED_MSG,
        ]
        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            with pytest.raises(NoHistoricalDataError):
                # Same-day range → 0 estimated bars → no segmentation
                await client.get_historical_ohlcv(SYMBOL, "1", start="2024-01-01", end="2024-01-01")

    @pytest.mark.asyncio
    async def test_intraday_range_boundaries_respected(self) -> None:
        """Fallback filter uses exact datetime boundaries, not date-only expansion.

        When start/end are UTC datetimes with an explicit time component,
        end_of_day_timestamp() returns the exact timestamp (no +86399 expansion).
        Bars outside the intraday window must be excluded from the fallback.
        """
        session_start = datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC)
        session_end = datetime(2024, 1, 2, 21, 0, 0, tzinfo=UTC)

        ts_in = session_start.timestamp() + 30 * 60  # 22:30 — inside window
        ts_before = session_start.timestamp() - 3600  # 21:00 — before window
        ts_after = session_end.timestamp() + 3600  # 22:00 next day — after window

        series: list[dict[str, Any]] = [
            {"i": 0, "v": [ts_before, 1.0, 2.0, 0.5, 1.5, 1.0]},
            {"i": 1, "v": [ts_in, 1.0, 2.0, 0.5, 1.5, 1.0]},
            {"i": 2, "v": [ts_after, 1.0, 2.0, 0.5, 1.5, 1.0]},
        ]
        msg: dict[str, Any] = {"m": "timescale_update", "p": ["cs_xxx", {"sds_1": {"s": series}}]}
        messages: list[dict[str, Any]] = [msg, SERIES_COMPLETED_MSG]

        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            result = await client.get_historical_ohlcv(
                SYMBOL, "1", start=session_start, end=session_end
            )

        assert len(result) == 1
        assert result[0].timestamp == ts_in

    @pytest.mark.asyncio
    async def test_multiple_timescale_updates_before_single_event(self) -> None:
        """Bars spread across multiple timescale_update messages are all captured in fallback."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=3, base_ts=_TS_JAN_2024),
            make_timescale_update(bars_count=4, base_ts=_TS_JAN_2024 + 1000),
            SERIES_COMPLETED_MSG,  # Single event — all 7 bars saved as fallback
        ]
        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            result = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2024-01-01", end="2024-12-31"
            )

        assert len(result) == 7


# ===========================================================================
# Fix 2 — inter_segment_delay in SegmentedFetchService
# ===========================================================================


class TestInterSegmentDelay:
    """
    Fix 2: asyncio.sleep() is injected between consecutive segment fetches
    when inter_segment_delay > 0.0. Skipped after the last segment.
    """

    @staticmethod
    def _service_with_delay(
        delay: float, n_segments: int
    ) -> tuple[SegmentedFetchService, AsyncMock]:
        """Return a service + mock where every segment returns 1 bar."""
        mock_client = AsyncMock(spec=OHLCV)
        mock_client._auth_manager = None
        mock_client._fetch_single_range = AsyncMock(
            side_effect=[[make_bar(float(i * 3600))] for i in range(n_segments)]
        )
        service = SegmentedFetchService(
            client=mock_client,
            max_bars_per_segment=1,
            inter_segment_delay=delay,
        )
        return service, mock_client

    @pytest.mark.asyncio
    async def test_delay_called_between_segments_not_after_last(self) -> None:
        """asyncio.sleep() is called N-1 times for N segments (skipped after last)."""
        n = 3
        service, _ = self._service_with_delay(delay=2.0, n_segments=n)

        with patch("tvkit.api.chart.services.segmented_fetch_service.asyncio.sleep") as mock_sleep:
            await service.fetch_all(
                SYMBOL,
                "1H",
                start=datetime(2024, 1, 1, tzinfo=UTC),
                end=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=n - 1),
            )

        assert mock_sleep.call_count == n - 1
        mock_sleep.assert_called_with(2.0)

    @pytest.mark.asyncio
    async def test_no_sleep_when_delay_is_zero(self) -> None:
        """asyncio.sleep() is never called when inter_segment_delay=0.0."""
        service, _ = self._service_with_delay(delay=0.0, n_segments=3)

        with patch("tvkit.api.chart.services.segmented_fetch_service.asyncio.sleep") as mock_sleep:
            await service.fetch_all(
                SYMBOL,
                "1H",
                start=datetime(2024, 1, 1, tzinfo=UTC),
                end=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=2),
            )

        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_segment_no_sleep(self) -> None:
        """A single-segment fetch never triggers a sleep."""
        mock_client = AsyncMock(spec=OHLCV)
        mock_client._auth_manager = None
        mock_client._fetch_single_range = AsyncMock(return_value=[make_bar(1000.0)])
        service = SegmentedFetchService(
            client=mock_client,
            max_bars_per_segment=MAX_BARS_REQUEST,
            inter_segment_delay=5.0,
        )

        with patch("tvkit.api.chart.services.segmented_fetch_service.asyncio.sleep") as mock_sleep:
            await service.fetch_all(
                SYMBOL,
                "1H",
                start=datetime(2024, 1, 1, tzinfo=UTC),
                end=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=1),
            )

        mock_sleep.assert_not_called()

    def test_default_delay_is_zero(self) -> None:
        """SegmentedFetchService constructor default inter_segment_delay is 0.0."""
        mock_client = MagicMock(spec=OHLCV)
        service = SegmentedFetchService(client=mock_client)
        assert service._inter_segment_delay == 0.0

    def test_constructor_stores_delay(self) -> None:
        """The delay value provided at construction is stored correctly."""
        mock_client = MagicMock(spec=OHLCV)
        service = SegmentedFetchService(client=mock_client, inter_segment_delay=3.5)
        assert service._inter_segment_delay == 3.5

    @pytest.mark.asyncio
    async def test_delay_value_passed_to_each_sleep_call(self) -> None:
        """The exact delay value is forwarded to every asyncio.sleep() call."""
        n = 4
        delay = 1.5
        service, _ = self._service_with_delay(delay=delay, n_segments=n)

        with patch("tvkit.api.chart.services.segmented_fetch_service.asyncio.sleep") as mock_sleep:
            await service.fetch_all(
                SYMBOL,
                "1H",
                start=datetime(2024, 1, 1, tzinfo=UTC),
                end=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=n - 1),
            )

        expected_calls = [call(delay)] * (n - 1)
        mock_sleep.assert_has_calls(expected_calls, any_order=False)

    @pytest.mark.asyncio
    async def test_delay_exactly_n_minus_one_calls(self) -> None:
        """For N segments, exactly N-1 sleep calls — confirmed for N=2, 3, 4."""
        for n in (2, 3, 4):
            service, _ = self._service_with_delay(delay=0.5, n_segments=n)
            with patch(
                "tvkit.api.chart.services.segmented_fetch_service.asyncio.sleep"
            ) as mock_sleep:
                await service.fetch_all(
                    SYMBOL,
                    "1H",
                    start=datetime(2024, 1, 1, tzinfo=UTC),
                    end=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=n - 1),
                )
            assert mock_sleep.call_count == n - 1, f"Expected {n - 1} calls for {n} segments"


# ===========================================================================
# Fix 3 — segment_delay public parameter on get_historical_ohlcv()
# ===========================================================================


class TestSegmentDelayParameter:
    """
    Fix 3: segment_delay is forwarded to SegmentedFetchService when the
    requested date range triggers segmentation.
    """

    @pytest.mark.asyncio
    async def test_segment_delay_forwarded_to_service(self) -> None:
        """segment_delay is passed as inter_segment_delay to SegmentedFetchService."""
        client = OHLCV()
        mock_service = AsyncMock(spec=SegmentedFetchService)
        mock_service.fetch_all = AsyncMock(return_value=[make_bar(float(_TS_JAN_2024))])

        start_dt = datetime(2024, 1, 1, tzinfo=UTC)
        end_dt = start_dt + timedelta(days=10)  # >5000 bars at 1-min → triggers segmentation

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()),
            patch(
                "tvkit.api.chart.ohlcv.SegmentedFetchService",
                return_value=mock_service,
            ) as mock_cls,
        ):
            await client.get_historical_ohlcv(
                SYMBOL, "1", start=start_dt, end=end_dt, segment_delay=2.5
            )

        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["inter_segment_delay"] == 2.5

    @pytest.mark.asyncio
    async def test_segment_delay_default_is_zero(self) -> None:
        """Omitting segment_delay defaults to 0.0 forwarded to SegmentedFetchService."""
        client = OHLCV()
        mock_service = AsyncMock(spec=SegmentedFetchService)
        mock_service.fetch_all = AsyncMock(return_value=[make_bar(float(_TS_JAN_2024))])

        start_dt = datetime(2024, 1, 1, tzinfo=UTC)
        end_dt = start_dt + timedelta(days=10)

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()),
            patch(
                "tvkit.api.chart.ohlcv.SegmentedFetchService",
                return_value=mock_service,
            ) as mock_cls,
        ):
            await client.get_historical_ohlcv(SYMBOL, "1", start=start_dt, end=end_dt)

        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs["inter_segment_delay"] == 0.0

    def test_get_historical_ohlcv_signature_has_segment_delay(self) -> None:
        """get_historical_ohlcv() signature includes segment_delay with default 0.0."""
        import inspect

        sig = inspect.signature(OHLCV.get_historical_ohlcv)
        param = sig.parameters.get("segment_delay")
        assert param is not None, "segment_delay parameter missing from get_historical_ohlcv"
        assert param.default == 0.0

    @pytest.mark.asyncio
    async def test_segment_delay_ignored_in_count_mode(self) -> None:
        """segment_delay has no effect in count mode (SegmentedFetchService not instantiated)."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=5),
            SERIES_COMPLETED_MSG,
        ]
        client = OHLCV()
        client._prepare_chart_session = AsyncMock()  # type: ignore[method-assign]
        client._session = _StreamingSession(  # type: ignore[assignment]
            symbol=SYMBOL,
            interval="1",
            bars_count=5,
            quote_session="qs_test",
            chart_session="cs_test",
        )
        client.connection_service = MagicMock()
        client.connection_service.get_data_stream = lambda: fake_stream(messages)
        client.connection_service.close = AsyncMock()

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()),
            patch("tvkit.api.chart.ohlcv.SegmentedFetchService") as mock_cls,
        ):
            result = await client.get_historical_ohlcv(
                SYMBOL, "1", bars_count=5, segment_delay=99.0
            )

        mock_cls.assert_not_called()
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_segment_delay_ignored_for_small_range(self) -> None:
        """segment_delay is ignored when the range fits within a single request."""
        start_dt = datetime(2024, 1, 1, tzinfo=UTC)
        end_dt = start_dt + timedelta(minutes=10)  # 10 bars — no segmentation

        create_bars = make_timescale_update(bars_count=2, base_ts=_TS_JAN_2024)
        modify_bars = make_timescale_update(bars_count=3, base_ts=_TS_JAN_2024 + 200)
        messages = [create_bars, SERIES_COMPLETED_MSG, modify_bars, SERIES_COMPLETED_MSG]

        client = _make_range_client(messages)

        with (
            patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()),
            patch("tvkit.api.chart.ohlcv.SegmentedFetchService") as mock_cls,
        ):
            await client.get_historical_ohlcv(
                SYMBOL, "1", start=start_dt, end=end_dt, segment_delay=5.0
            )

        mock_cls.assert_not_called()


# ===========================================================================
# Regression: backward compatibility
# ===========================================================================


class TestBackwardCompatibility:
    """
    All three fixes must be 100% backward-compatible — existing call sites
    must continue to work without modification.
    """

    def test_segmented_fetch_service_zero_arg_construction(self) -> None:
        """SegmentedFetchService(client) — zero extra args still works."""
        mock_client = MagicMock(spec=OHLCV)
        service = SegmentedFetchService(client=mock_client)
        assert service._inter_segment_delay == 0.0

    def test_segmented_fetch_service_positional_max_bars_unchanged(self) -> None:
        """SegmentedFetchService(client, 5000) — second positional arg unchanged."""
        mock_client = MagicMock(spec=OHLCV)
        service = SegmentedFetchService(client=mock_client, max_bars_per_segment=5000)
        assert service._max_bars_per_segment == 5000
        assert service._inter_segment_delay == 0.0

    @pytest.mark.asyncio
    async def test_count_mode_existing_call_site_unchanged(self) -> None:
        """get_historical_ohlcv('X', '1D', bars_count=500) — existing signature works."""
        messages: list[dict[str, Any]] = [
            make_timescale_update(bars_count=10),
            SERIES_COMPLETED_MSG,
        ]
        client = OHLCV()
        client._prepare_chart_session = AsyncMock()  # type: ignore[method-assign]
        client._session = _StreamingSession(  # type: ignore[assignment]
            symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=500,
            quote_session="qs_test",
            chart_session="cs_test",
        )
        client.connection_service = MagicMock()
        client.connection_service.get_data_stream = lambda: fake_stream(messages)
        client.connection_service.close = AsyncMock()

        with patch.multiple(
            "tvkit.api.chart.ohlcv",
            validate_symbols=AsyncMock(return_value=True),
            normalize_symbol=MagicMock(return_value="NASDAQ:AAPL"),
            validate_interval=MagicMock(),
        ):
            result = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=500)

        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_range_mode_two_event_path_unchanged(self) -> None:
        """get_historical_ohlcv(start=..., end=...) — two-event path returns correct bars."""
        create_bars = make_timescale_update(bars_count=3, base_ts=_TS_JAN_2024)
        modify_bars = make_timescale_update(bars_count=8, base_ts=_TS_JAN_2024 + 5_000)
        messages = [create_bars, SERIES_COMPLETED_MSG, modify_bars, SERIES_COMPLETED_MSG]

        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            result = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2024-01-01", end="2024-12-31"
            )

        assert len(result) == 8

    @pytest.mark.asyncio
    async def test_range_mode_no_segment_delay_arg_works(self) -> None:
        """Calling get_historical_ohlcv without segment_delay uses default 0.0 silently."""
        create_bars = make_timescale_update(bars_count=2, base_ts=_TS_JAN_2024)
        modify_bars = make_timescale_update(bars_count=4, base_ts=_TS_JAN_2024 + 1000)
        messages = [create_bars, SERIES_COMPLETED_MSG, modify_bars, SERIES_COMPLETED_MSG]

        client = _make_range_client(messages)

        with patch.multiple("tvkit.api.chart.ohlcv", **_make_patches()):
            result = await client.get_historical_ohlcv(
                SYMBOL, "1", start="2024-01-01", end="2024-12-31"
            )

        assert len(result) == 4
