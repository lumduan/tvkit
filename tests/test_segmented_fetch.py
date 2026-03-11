"""
Tests for SegmentedFetchService.

Covers:
- Happy path: single-segment, multi-segment merge, sort, deduplication
- Edge cases: empty segment ([] return), NoHistoricalDataError skipped, many segments,
  zero-length range, start > end raises, str input raises
- Failure path: SegmentedFetchError raised with correct attributes (index, cause,
  segment_start, segment_end, total_segments), NoHistoricalDataError treated as empty
- Deduplication algorithm: first-occurrence wins, ascending sort, intra-segment dedup
- Boundary bar deduplication: end-to-end segment boundary overlap
- Recursion guard: _fetch_single_range called, get_historical_ohlcv NOT called

No live WebSocket connections — all external I/O is mocked.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from tvkit.api.chart.exceptions import NoHistoricalDataError, SegmentedFetchError
from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.chart.services.segmented_fetch_service import SegmentedFetchService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


def make_bar(ts: float, volume: float = 100.0) -> OHLCVBar:
    """Create a minimal OHLCVBar. ``volume`` lets dedup tests verify which bar was kept."""
    return OHLCVBar(timestamp=ts, open=1.0, high=2.0, low=0.5, close=1.5, volume=volume)


def _service_with_effects(*effects: object) -> tuple[SegmentedFetchService, AsyncMock]:
    """
    Return a (SegmentedFetchService, mock_client) pair wired to ``effects``.

    Each positional argument becomes one entry in ``side_effect``:
    - A list  → _fetch_single_range returns that list on this call
    - An Exception subclass instance → _fetch_single_range raises it on this call
    """
    mock_client = AsyncMock(spec=OHLCV)
    mock_client._fetch_single_range = AsyncMock(side_effect=list(effects))
    service = SegmentedFetchService(client=mock_client)
    return service, mock_client


def _service_1bar_per_segment(*effects: object) -> SegmentedFetchService:
    """
    Return a SegmentedFetchService with max_bars_per_segment=1 (one segment per bar slot).
    Used to produce predictable multi-segment scenarios without a large date range.
    """
    mock_client = AsyncMock(spec=OHLCV)
    mock_client._fetch_single_range = AsyncMock(side_effect=list(effects))
    return SegmentedFetchService(client=mock_client, max_bars_per_segment=1)


# ---------------------------------------------------------------------------
# TestFetchAllHappyPath
# ---------------------------------------------------------------------------


class TestFetchAllHappyPath:
    """SegmentedFetchService.fetch_all() — normal successful operation."""

    @pytest.mark.asyncio
    async def test_single_segment_returns_bars(self) -> None:
        """A small range produces one segment; bars are returned in ascending order."""
        bar1 = make_bar(1000.0)
        bar2 = make_bar(1060.0)
        service, _ = _service_with_effects([bar1, bar2])
        result = await service.fetch_all(
            "NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1)
        )
        assert len(result) == 2
        assert result[0].timestamp == 1000.0
        assert result[1].timestamp == 1060.0

    @pytest.mark.asyncio
    async def test_multi_segment_merges_bars(self) -> None:
        """Each of two segments returns 2 bars; all 4 are merged and sorted in the result."""
        service = _service_1bar_per_segment(
            [make_bar(100.0), make_bar(200.0)],
            [make_bar(300.0), make_bar(400.0)],
        )
        result = await service.fetch_all(
            "NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1)
        )
        assert [b.timestamp for b in result] == [100.0, 200.0, 300.0, 400.0]

    @pytest.mark.asyncio
    async def test_result_sorted_ascending(self) -> None:
        """Bars returned from different segments are sorted ascending in the final result."""
        service = _service_1bar_per_segment(
            [make_bar(200.0)],  # segment 1 has a later timestamp
            [make_bar(100.0)],  # segment 2 has an earlier timestamp
        )
        result = await service.fetch_all(
            "NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1)
        )
        assert result[0].timestamp < result[1].timestamp

    @pytest.mark.asyncio
    async def test_boundary_duplicate_removed(self) -> None:
        """A bar that appears in two segments (boundary overlap) is deduplicated to one."""
        service = _service_1bar_per_segment(
            [make_bar(100.0)],
            [make_bar(100.0)],  # same timestamp — simulates boundary bleed
        )
        result = await service.fetch_all(
            "NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1)
        )
        assert len(result) == 1
        assert result[0].timestamp == 100.0


# ---------------------------------------------------------------------------
# TestFetchAllEdgeCases
# ---------------------------------------------------------------------------


class TestFetchAllEdgeCases:
    """SegmentedFetchService.fetch_all() — unusual but valid inputs."""

    @pytest.mark.asyncio
    async def test_empty_list_segment_skipped(self) -> None:
        """A segment returning [] (empty list) is skipped; subsequent segments still processed."""
        bar = make_bar(500.0)
        service = _service_1bar_per_segment([], [bar])
        result = await service.fetch_all(
            "NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1)
        )
        assert len(result) == 1
        assert result[0].timestamp == 500.0

    @pytest.mark.asyncio
    async def test_no_data_error_segment_skipped(self) -> None:
        """A segment raising NoHistoricalDataError is skipped; later segments still processed."""
        bar = make_bar(500.0)
        service = _service_1bar_per_segment(NoHistoricalDataError("holiday"), [bar])
        result = await service.fetch_all(
            "NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1)
        )
        assert len(result) == 1
        assert result[0].timestamp == 500.0

    @pytest.mark.asyncio
    async def test_all_segments_empty_returns_empty_list(self) -> None:
        """When every segment raises NoHistoricalDataError, fetch_all returns [] without raising."""
        mock_client = AsyncMock(spec=OHLCV)
        mock_client._fetch_single_range = AsyncMock(side_effect=NoHistoricalDataError("no data"))
        service = SegmentedFetchService(client=mock_client, max_bars_per_segment=1)
        result = await service.fetch_all(
            "NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1)
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_many_segments_processed_correctly(self) -> None:
        """
        A range producing 20 segments, each returning 1 bar, yields 20 bars in the result.
        Exercises the full loop to catch any off-by-one or premature-exit bugs.
        """
        num_segments = 20
        # With max_bars=1, interval_seconds=3600:
        #   segment_delta = 1*3600 - 3600 = 0 → each segment is a single point.
        #   cursor advances by 3600s per step → (num_segments-1) * 3600s range needed.
        end = _T0 + timedelta(hours=num_segments - 1)
        bars = [make_bar(float(i * 3600)) for i in range(num_segments)]
        mock_client = AsyncMock(spec=OHLCV)
        mock_client._fetch_single_range = AsyncMock(side_effect=[[b] for b in bars])
        service = SegmentedFetchService(client=mock_client, max_bars_per_segment=1)
        result = await service.fetch_all("NASDAQ:AAPL", "1H", start=_T0, end=end)
        assert len(result) == num_segments

    @pytest.mark.asyncio
    async def test_zero_length_range_returns_one_segment(self) -> None:
        """start == end is valid — segment_time_range returns 1 segment covering the single point."""
        bar = make_bar(float(_T0.timestamp()))
        service, _ = _service_with_effects([bar])
        result = await service.fetch_all("NASDAQ:AAPL", "1H", start=_T0, end=_T0)
        assert result == [bar]

    @pytest.mark.asyncio
    async def test_start_after_end_raises_value_error(self) -> None:
        """start > end is rejected by segment_time_range() with ValueError."""
        service, _ = _service_with_effects([])
        with pytest.raises(ValueError):
            await service.fetch_all(
                "NASDAQ:AAPL",
                "1H",
                start=_T0 + timedelta(hours=1),  # start is AFTER end
                end=_T0,
            )

    @pytest.mark.asyncio
    async def test_str_start_end_raises_type_error(self) -> None:
        """
        fetch_all() requires datetime objects, not strings. Normalization from strings
        is OHLCV.get_historical_ohlcv()'s responsibility (via _to_utc_datetime()).
        Passing strings directly raises TypeError from datetime arithmetic.
        """
        service, _ = _service_with_effects([])
        with pytest.raises(TypeError):
            await service.fetch_all(
                "NASDAQ:AAPL",
                "1H",
                start="2024-01-01",  # type: ignore[arg-type]
                end="2024-02-01",  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# TestFetchAllFailure
# ---------------------------------------------------------------------------


class TestFetchAllFailure:
    """SegmentedFetchService.fetch_all() — failure and error-wrapping behaviour."""

    @pytest.mark.asyncio
    async def test_segment_failure_raises_segmented_fetch_error(self) -> None:
        """A RuntimeError from _fetch_single_range is wrapped in SegmentedFetchError."""
        service, _ = _service_with_effects(RuntimeError("network timeout"))
        with pytest.raises(SegmentedFetchError):
            await service.fetch_all("NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1))

    @pytest.mark.asyncio
    async def test_error_includes_segment_index(self) -> None:
        """The first segment failing sets segment_index == 1."""
        service, _ = _service_with_effects(RuntimeError("fail"))
        with pytest.raises(SegmentedFetchError) as exc_info:
            await service.fetch_all("NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1))
        assert exc_info.value.segment_index == 1

    @pytest.mark.asyncio
    async def test_error_includes_cause(self) -> None:
        """exc.cause is the original exception instance that triggered the failure."""
        original = RuntimeError("root cause")
        service, _ = _service_with_effects(original)
        with pytest.raises(SegmentedFetchError) as exc_info:
            await service.fetch_all("NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1))
        assert exc_info.value.cause is original

    @pytest.mark.asyncio
    async def test_error_includes_segment_context(self) -> None:
        """
        exc.segment_start, exc.segment_end, and exc.total_segments are populated.
        These attributes are critical for diagnosing production failures.
        """
        service, _ = _service_with_effects(RuntimeError("fail"))
        start = _T0
        end = _T0 + timedelta(hours=1)
        with pytest.raises(SegmentedFetchError) as exc_info:
            await service.fetch_all("NASDAQ:AAPL", "1H", start=start, end=end)
        exc = exc_info.value
        assert exc.segment_start >= start
        assert exc.segment_end <= end
        assert exc.total_segments >= 1

    @pytest.mark.asyncio
    async def test_known_no_data_error_treated_as_empty(self) -> None:
        """NoHistoricalDataError (expected: weekend/holiday) is NOT wrapped in SegmentedFetchError."""
        service, _ = _service_with_effects(NoHistoricalDataError("holiday"))
        result = await service.fetch_all(
            "NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1)
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_unexpected_exception_wrapped_as_segmented_fetch_error(self) -> None:
        """Any unexpected exception type is wrapped in SegmentedFetchError, not re-raised bare."""
        service, _ = _service_with_effects(ValueError("unexpected"))
        with pytest.raises(SegmentedFetchError) as exc_info:
            await service.fetch_all("NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1))
        assert isinstance(exc_info.value.cause, ValueError)


# ---------------------------------------------------------------------------
# TestDeduplicateAndSort
# ---------------------------------------------------------------------------


class TestDeduplicateAndSort:
    """SegmentedFetchService._deduplicate_and_sort() — deduplication and sort invariants."""

    def test_deduplicates_first_occurrence_wins(self) -> None:
        """When two bars share a timestamp, the first one in input order is kept."""
        bar_first = make_bar(ts=1.0, volume=10.0)
        bar_dup = make_bar(ts=1.0, volume=999.0)  # same ts, different volume
        result = SegmentedFetchService._deduplicate_and_sort([bar_first, bar_dup])
        assert len(result) == 1
        assert result[0].volume == 10.0  # first occurrence retained

    def test_deduplicates_within_single_segment(self) -> None:
        """Intra-segment duplicates (e.g. API bug returning same bar twice) are also removed."""
        bar = make_bar(ts=42.0, volume=7.0)
        bar_dup = make_bar(ts=42.0, volume=8.0)
        result = SegmentedFetchService._deduplicate_and_sort([bar, bar_dup])
        assert len(result) == 1
        assert result[0].volume == 7.0  # first occurrence kept

    def test_sorts_ascending(self) -> None:
        """Bars are sorted ascending by timestamp regardless of input order."""
        bars = [make_bar(3.0), make_bar(1.0), make_bar(2.0)]
        result = SegmentedFetchService._deduplicate_and_sort(bars)
        assert [b.timestamp for b in result] == [1.0, 2.0, 3.0]

    def test_empty_input_returns_empty_list(self) -> None:
        """Empty input returns [] without raising."""
        assert SegmentedFetchService._deduplicate_and_sort([]) == []

    def test_single_bar_passthrough(self) -> None:
        """A list of one bar is returned unchanged."""
        bar = make_bar(42.0)
        result = SegmentedFetchService._deduplicate_and_sort([bar])
        assert result == [bar]

    def test_already_sorted_input_unchanged(self) -> None:
        """Already-sorted input is returned in the same order (no accidental reversal)."""
        bars = [make_bar(1.0), make_bar(2.0), make_bar(3.0)]
        result = SegmentedFetchService._deduplicate_and_sort(bars)
        assert [b.timestamp for b in result] == [1.0, 2.0, 3.0]


# ---------------------------------------------------------------------------
# TestBoundaryBarDeduplication
# ---------------------------------------------------------------------------


class TestBoundaryBarDeduplication:
    """
    End-to-end test for segment boundary bar deduplication.

    TradingView may return the boundary bar in both the ending and starting segment.
    This verifies the full pipeline — fetch_all + _deduplicate_and_sort — removes the
    duplicate and keeps exactly one copy (first-occurrence / earlier segment wins).
    """

    @pytest.mark.asyncio
    async def test_boundary_bar_deduplicated_between_segments(self) -> None:
        """
        Segment 1 returns [ts=100, ts=200]; segment 2 returns [ts=200, ts=300].
        ts=200 is the boundary bar that bleeds into both segments.

        Expected:
        - Merged result: [ts=100, ts=200, ts=300] — 3 bars, not 4
        - ts=200 from segment 1 (volume=2.0) is kept; segment 2's copy (volume=99.0) dropped
        """
        bar_100 = make_bar(100.0, volume=1.0)
        bar_200_seg1 = make_bar(200.0, volume=2.0)  # authoritative — earlier segment
        bar_200_seg2 = make_bar(200.0, volume=99.0)  # duplicate — later segment
        bar_300 = make_bar(300.0, volume=3.0)

        service = _service_1bar_per_segment(
            [bar_100, bar_200_seg1],
            [bar_200_seg2, bar_300],
        )
        result = await service.fetch_all(
            "NASDAQ:AAPL", "1H", start=_T0, end=_T0 + timedelta(hours=1)
        )

        assert len(result) == 3
        assert [b.timestamp for b in result] == [100.0, 200.0, 300.0]
        boundary = next(b for b in result if b.timestamp == 200.0)
        assert boundary.volume == 2.0  # earlier segment's bar kept


# ---------------------------------------------------------------------------
# TestRecursionGuard
# ---------------------------------------------------------------------------


class TestRecursionGuard:
    """
    Architectural invariant: SegmentedFetchService calls _fetch_single_range(), NOT get_historical_ohlcv().

    Calling get_historical_ohlcv() from within SegmentedFetchService would cause
    infinite recursion for any segment whose estimated bar count exceeds MAX_BARS_REQUEST,
    since the public method re-checks _needs_segmentation() and re-enters SegmentedFetchService.

    This test acts as an architecture regression guard — it fails immediately if
    someone accidentally changes the call site.
    """

    @pytest.mark.asyncio
    async def test_calls_fetch_single_range_not_public_api(self) -> None:
        """fetch_all() MUST call client._fetch_single_range(), never client.get_historical_ohlcv()."""
        mock_client = AsyncMock(spec=OHLCV)
        mock_client._fetch_single_range = AsyncMock(return_value=[make_bar(1000.0)])
        service = SegmentedFetchService(client=mock_client)

        await service.fetch_all(
            "NASDAQ:AAPL",
            "1H",
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 2, tzinfo=UTC),
        )

        mock_client._fetch_single_range.assert_called()
        mock_client.get_historical_ohlcv.assert_not_called()
