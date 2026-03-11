"""Tests for TimeSegment, segment_time_range(), and _to_utc_datetime()."""

import dataclasses
from datetime import UTC, datetime, timedelta, timezone

import pytest

from tvkit.api.chart.exceptions import RangeTooLargeError
from tvkit.api.chart.utils import (
    MAX_SEGMENTS,
    TimeSegment,
    _to_utc_datetime,
    segment_time_range,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

T0 = datetime(2023, 1, 1, tzinfo=UTC)


def dt(days: float = 0, seconds: float = 0) -> datetime:
    """Return a UTC datetime offset from T0."""
    return T0 + timedelta(days=days, seconds=seconds)


# ---------------------------------------------------------------------------
# TestTimeSegment
# ---------------------------------------------------------------------------


class TestTimeSegment:
    def test_is_frozen_dataclass(self) -> None:
        assert dataclasses.is_dataclass(TimeSegment)
        seg = TimeSegment(start=T0, end=dt(days=1))
        with pytest.raises(dataclasses.FrozenInstanceError):
            seg.start = dt(days=2)  # type: ignore[misc]

    def test_attributes_accessible(self) -> None:
        start = dt(days=0)
        end = dt(days=1)
        seg = TimeSegment(start=start, end=end)
        assert seg.start == start
        assert seg.end == end

    def test_equality(self) -> None:
        seg_a = TimeSegment(start=T0, end=dt(days=1))
        seg_b = TimeSegment(start=T0, end=dt(days=1))
        seg_c = TimeSegment(start=T0, end=dt(days=2))
        assert seg_a == seg_b
        assert seg_a != seg_c

    def test_hashable(self) -> None:
        seg = TimeSegment(start=T0, end=dt(days=1))
        s: set[TimeSegment] = {seg}
        assert seg in s
        d: dict[TimeSegment, int] = {seg: 42}
        assert d[seg] == 42


# ---------------------------------------------------------------------------
# TestSegmentTimeRange
# ---------------------------------------------------------------------------


class TestSegmentTimeRange:
    def test_single_segment_when_range_fits(self) -> None:
        # 1-minute interval, max_bars=5 → segment covers 5 minutes
        # Range of 4 minutes fits in one segment
        start = T0
        end = dt(seconds=240)  # 4 minutes
        segs = segment_time_range(start, end, interval_seconds=60, max_bars=5)
        assert len(segs) == 1
        assert segs[0].start == start
        assert segs[0].end == end

    def test_multiple_segments_for_large_range(self) -> None:
        # 1-minute bars, max_bars=5000 → segment = 300,000s ≈ 3.47 days
        # 90-day range → multiple segments
        start = T0
        end = dt(days=90)
        segs = segment_time_range(start, end, interval_seconds=60, max_bars=5000)
        assert len(segs) > 1

    def test_last_segment_clamped_to_end(self) -> None:
        start = T0
        end = dt(days=10)
        segs = segment_time_range(start, end, interval_seconds=60, max_bars=5000)
        assert segs[-1].end == end

    def test_start_equals_end_returns_one_segment(self) -> None:
        segs = segment_time_range(T0, T0, interval_seconds=60, max_bars=5000)
        assert len(segs) == 1
        assert segs[0].start == T0
        assert segs[0].end == T0

    def test_start_after_end_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be after end"):
            segment_time_range(dt(days=1), T0, interval_seconds=60, max_bars=5000)

    def test_zero_interval_raises(self) -> None:
        with pytest.raises(ValueError, match="interval_seconds must be > 0"):
            segment_time_range(T0, dt(days=1), interval_seconds=0, max_bars=5000)

    def test_negative_interval_raises(self) -> None:
        with pytest.raises(ValueError, match="interval_seconds must be > 0"):
            segment_time_range(T0, dt(days=1), interval_seconds=-60, max_bars=5000)

    def test_zero_max_bars_raises(self) -> None:
        with pytest.raises(ValueError, match="max_bars must be > 0"):
            segment_time_range(T0, dt(days=1), interval_seconds=60, max_bars=0)

    def test_exceeds_max_segments_raises(self) -> None:
        # 1-second interval over 200 days → >> 2000 segments
        # segment_duration = 1 * 5000 = 5000s ≈ 83 minutes per segment
        # 200 days = 17,280,000s → ~3456 segments >> MAX_SEGMENTS
        start = T0
        end = dt(days=200)
        with pytest.raises(RangeTooLargeError):
            segment_time_range(start, end, interval_seconds=1, max_bars=5000)

    def test_exactly_max_segments_does_not_raise(self) -> None:
        # Each segment covers exactly one bar (max_bars=1, segment_delta=0 → start==end).
        # Cursor advances by interval=60s each iteration.
        # To get exactly MAX_SEGMENTS segments: end = T0 + (MAX_SEGMENTS - 1) * 60s
        interval = 60
        max_bars = 1
        total_secs = (MAX_SEGMENTS - 1) * interval
        end = T0 + timedelta(seconds=total_secs)
        segs = segment_time_range(T0, end, interval_seconds=interval, max_bars=max_bars)
        assert len(segs) == MAX_SEGMENTS
        assert segs[0].start == T0
        assert segs[-1].end == end

    def test_exact_max_bars_single_segment(self) -> None:
        # Range spanning exactly max_bars bars → one segment, end clamped correctly.
        # With max_bars=5000, interval=60: segment_delta = (5000*60 - 60) = 299,940s
        # A range of 299,940s fits in one segment.
        interval = 60
        max_bars = 5000
        end = T0 + timedelta(seconds=(max_bars - 1) * interval)
        segs = segment_time_range(T0, end, interval_seconds=interval, max_bars=max_bars)
        assert len(segs) == 1
        assert segs[0].start == T0
        assert segs[0].end == end

    def test_rangetoolargeerror_is_valueerror(self) -> None:
        assert issubclass(RangeTooLargeError, ValueError)


# ---------------------------------------------------------------------------
# TestSegmentBoundaryAlgebra
# ---------------------------------------------------------------------------


class TestSegmentBoundaryAlgebra:
    """Verify the mathematical invariants of segment boundaries."""

    # Use a small max_bars to produce multiple segments over short ranges.
    INTERVAL = 60  # 1 minute
    MAX_BARS = 3  # 3 bars per segment → segment_duration = 180s, segment_delta = 120s

    def _segs(self, days: float) -> list[TimeSegment]:
        return segment_time_range(
            T0,
            dt(days=days),
            interval_seconds=self.INTERVAL,
            max_bars=self.MAX_BARS,
        )

    def test_segments_are_non_overlapping(self) -> None:
        segs = self._segs(1)
        for i in range(len(segs) - 1):
            assert segs[i].end < segs[i + 1].start

    def test_no_gap_between_segments(self) -> None:
        segs = self._segs(1)
        interval_delta = timedelta(seconds=self.INTERVAL)
        for i in range(len(segs) - 1):
            gap = segs[i + 1].start - segs[i].end
            assert gap == interval_delta

    def test_all_segments_cover_full_range(self) -> None:
        end = dt(days=1)
        segs = segment_time_range(T0, end, interval_seconds=self.INTERVAL, max_bars=self.MAX_BARS)
        assert segs[0].start == T0
        assert segs[-1].end == end

    def test_cursor_advances_by_interval(self) -> None:
        segs = self._segs(1)
        interval_delta = timedelta(seconds=self.INTERVAL)
        for i in range(len(segs) - 1):
            assert segs[i + 1].start == segs[i].end + interval_delta

    def test_single_bar_range(self) -> None:
        # Range of exactly one interval → one segment covering one bar (start != end).
        end = dt(seconds=self.INTERVAL)
        segs = segment_time_range(T0, end, interval_seconds=self.INTERVAL, max_bars=self.MAX_BARS)
        assert len(segs) == 1
        assert segs[0].start == T0
        assert segs[0].end == end

    def test_exact_multiple_of_segment_duration(self) -> None:
        # segment_duration = 3 * 60 = 180s; segment_delta = 120s
        # Range: T0 → T0 + (2 * 180 - 60) = T0 + 300s
        # Segment 1: [T0, T0+120s], cursor → T0+180s
        # Segment 2: [T0+180s, T0+300s], cursor → T0+360s > end → stop
        segment_duration = self.MAX_BARS * self.INTERVAL  # 180s
        end = T0 + timedelta(seconds=2 * segment_duration - self.INTERVAL)
        segs = segment_time_range(T0, end, interval_seconds=self.INTERVAL, max_bars=self.MAX_BARS)
        assert len(segs) == 2
        assert segs[-1].end == end

    def test_segment_size_correctness(self) -> None:
        # All non-last segments must have duration == segment_duration - interval_seconds.
        segs = self._segs(1)
        expected_duration = timedelta(seconds=self.MAX_BARS * self.INTERVAL - self.INTERVAL)
        for seg in segs[:-1]:
            assert seg.end - seg.start == expected_duration


# ---------------------------------------------------------------------------
# TestToUtcDatetime
# ---------------------------------------------------------------------------


class TestToUtcDatetime:
    def test_aware_datetime_passthrough(self) -> None:
        aware = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        result = _to_utc_datetime(aware)
        assert result.tzinfo is not None
        assert int(result.timestamp()) == int(aware.timestamp())

    def test_naive_datetime_assigned_utc(self) -> None:
        naive = datetime(2024, 6, 15, 12, 0, 0)
        result = _to_utc_datetime(naive)
        assert result.tzinfo == UTC

    def test_non_utc_aware_datetime_converted(self) -> None:
        # A UTC+7 datetime representing midnight local time.
        tz_plus7 = timezone(timedelta(hours=7))
        dt_local = datetime(2024, 1, 1, 7, 0, 0, tzinfo=tz_plus7)
        result = _to_utc_datetime(dt_local)
        assert result.tzinfo == UTC
        # 2024-01-01 07:00 UTC+7 == 2024-01-01 00:00 UTC
        assert result == datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)

    def test_iso_string_with_z_suffix(self) -> None:
        result = _to_utc_datetime("2024-01-01T00:00:00Z")
        assert result == datetime(2024, 1, 1, tzinfo=UTC)

    def test_iso_date_string(self) -> None:
        result = _to_utc_datetime("2024-01-01")
        assert result == datetime(2024, 1, 1, tzinfo=UTC)

    def test_invalid_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            _to_utc_datetime(12345)  # type: ignore[arg-type]

    def test_invalid_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _to_utc_datetime("not-a-date")
