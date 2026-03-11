"""
Tests for the utils module, specifically for timestamp conversion functionality
and chart utility functions (to_unix_timestamp, build_range_param, validate_interval,
interval_to_seconds).
"""

from datetime import UTC, datetime

import pytest

from tvkit.api.chart.utils import build_range_param, interval_to_seconds, to_unix_timestamp
from tvkit.api.utils import convert_timestamp_to_iso


class TestTimestampConversion:
    """Test cases for convert_timestamp_to_iso() in tvkit.api.utils."""

    @pytest.mark.parametrize(
        "timestamp,expected",
        [
            (0.0, "1970-01-01T00:00:00+00:00"),  # epoch
            (1640995200.0, "2022-01-01T00:00:00+00:00"),  # 2022-01-01T00:00:00Z
            (1753436820.0, "2025-07-25T09:47:00+00:00"),  # 2025-07-25T09:47:00Z
        ],
    )
    def test_known_timestamps_produce_correct_iso_strings(
        self, timestamp: float, expected: str
    ) -> None:
        """Known unix timestamps map to the correct UTC ISO 8601 string."""
        assert convert_timestamp_to_iso(timestamp) == expected

    def test_output_is_valid_iso_8601_format(self) -> None:
        """Output contains all required ISO 8601 structural components."""
        result: str = convert_timestamp_to_iso(1753436820.0)  # 2025-07-25T09:47:00Z

        assert len(result) >= 19  # minimum ISO format length
        assert result.count("T") == 1  # date-time separator
        assert result.count("+") == 1  # timezone offset
        assert result.count(":") >= 2  # time separators
        assert result.count("-") >= 2  # date separators
        assert result.endswith("+00:00")

    def test_fractional_seconds_are_accepted(self) -> None:
        """Fractional-second timestamps do not raise; result reflects the whole-second value."""
        result: str = convert_timestamp_to_iso(1640995200.5)  # 2022-01-01T00:00:00.5Z
        assert result.startswith("2022-01-01T00:00:00")
        assert "+00:00" in result

    def test_roundtrip_consistency(self) -> None:
        """Parsing the output ISO string back to a datetime recovers the original timestamp."""
        timestamp: float = 1753436820.0  # 2025-07-25T09:47:00Z
        iso_string: str = convert_timestamp_to_iso(timestamp)

        parsed_dt: datetime = datetime.fromisoformat(iso_string)
        back_to_timestamp: float = parsed_dt.timestamp()

        assert abs(back_to_timestamp - timestamp) < 0.001

    def test_timezone_is_always_utc(self) -> None:
        """All outputs end with '+00:00' regardless of the input value."""
        for timestamp in (0.0, 1640995200.0, 1753436820.0):
            assert convert_timestamp_to_iso(timestamp).endswith("+00:00")

    def test_int_and_float_produce_identical_results(self) -> None:
        """Python accepts int where float is annotated; both inputs yield the same ISO string."""
        ts_int: int = 1640995200  # 2022-01-01T00:00:00Z
        ts_float: float = 1640995200.0
        # int is accepted by Python duck typing even though the annotation is float
        assert convert_timestamp_to_iso(ts_int) == convert_timestamp_to_iso(ts_float)  # type: ignore[arg-type]


class TestToUnixTimestamp:
    """Tests for to_unix_timestamp() in tvkit.api.chart.utils."""

    def test_datetime_utc(self) -> None:
        """Timezone-aware UTC datetime converts to correct Unix timestamp."""
        dt: datetime = datetime(2024, 1, 1, tzinfo=UTC)
        assert to_unix_timestamp(dt) == 1704067200

    def test_naive_datetime_treated_as_utc_no_raise(self) -> None:
        """Naive datetime is assigned UTC without raising; result matches explicit UTC."""
        naive: datetime = datetime(2024, 1, 1)
        aware: datetime = datetime(2024, 1, 1, tzinfo=UTC)
        assert to_unix_timestamp(naive) == to_unix_timestamp(aware)

    def test_iso_string_date_only(self) -> None:
        """Date-only ISO string parses to midnight UTC."""
        assert to_unix_timestamp("2024-01-01") == 1704067200

    def test_iso_string_with_time_and_tz(self) -> None:
        """Full ISO 8601 string with explicit timezone converts correctly."""
        assert to_unix_timestamp("2024-01-01T00:00:00+00:00") == 1704067200

    def test_iso_string_z_suffix(self) -> None:
        """ISO string ending in 'Z' is normalized and parsed correctly."""
        assert to_unix_timestamp("2024-01-01T00:00:00Z") == 1704067200

    def test_microsecond_truncation(self) -> None:
        """Microseconds are truncated (not rounded) to integer seconds."""
        dt_no_us: datetime = datetime(2024, 1, 1, tzinfo=UTC)
        dt_with_us: datetime = datetime(2024, 1, 1, 0, 0, 0, 999999, tzinfo=UTC)
        assert to_unix_timestamp(dt_no_us) == to_unix_timestamp(dt_with_us)

    def test_invalid_string_raises_value_error(self) -> None:
        """Non-ISO string raises ValueError from fromisoformat."""
        with pytest.raises(ValueError):
            to_unix_timestamp("not-a-date")

    def test_invalid_type_raises_type_error(self) -> None:
        """Non-datetime/str input raises TypeError with informative message."""
        with pytest.raises(TypeError, match="got 'int'"):
            to_unix_timestamp(1704067200)  # type: ignore[arg-type]

    def test_iso_string_with_time_no_tz_treated_as_utc(self) -> None:
        """ISO string with time component but no tz is treated as UTC (no raise)."""
        # "2024-01-01T06:00:00" has no tz — assigned UTC same as naive datetime
        result: int = to_unix_timestamp("2024-01-01T06:00:00")
        expected: int = to_unix_timestamp(datetime(2024, 1, 1, 6, 0, 0, tzinfo=UTC))
        assert result == expected


class TestBuildRangeParam:
    """Tests for build_range_param() in tvkit.api.chart.utils."""

    def test_valid_string_inputs_returns_r_prefix(self) -> None:
        """Valid start/end strings produce correct 'r,<from>:<to>' format."""
        result: str = build_range_param("2024-01-01", "2024-12-31")
        assert result.startswith("r,")
        from_ts, to_ts = result[2:].split(":")
        assert int(from_ts) == 1704067200
        assert int(to_ts) == 1735603200

    def test_same_day_is_valid(self) -> None:
        """start == end is valid (single-day intraday fetch)."""
        result: str = build_range_param("2024-06-15", "2024-06-15")
        parts: list[str] = result[2:].split(":")
        assert parts[0] == parts[1]

    def test_start_after_end_raises_value_error(self) -> None:
        """start > end raises ValueError before any WebSocket call."""
        with pytest.raises(ValueError, match="must not be after"):
            build_range_param("2024-12-31", "2024-01-01")

    def test_datetime_inputs(self) -> None:
        """datetime objects are accepted directly."""
        start: datetime = datetime(2024, 1, 1, tzinfo=UTC)
        end: datetime = datetime(2024, 12, 31, tzinfo=UTC)
        result: str = build_range_param(start, end)
        assert result == "r,1704067200:1735603200"

    def test_mixed_datetime_and_string_inputs(self) -> None:
        """Mix of datetime and str inputs is accepted."""
        start: datetime = datetime(2024, 1, 1, tzinfo=UTC)
        result: str = build_range_param(start, "2024-12-31")
        assert result.startswith("r,1704067200:")

    def test_naive_datetime_and_aware_datetime_mix(self) -> None:
        """Naive datetime in range param is assigned UTC without raising."""
        naive_start: datetime = datetime(2024, 1, 1)  # no tz
        aware_end: datetime = datetime(2024, 12, 31, tzinfo=UTC)
        result: str = build_range_param(naive_start, aware_end)
        # naive is assigned UTC — same result as explicit UTC
        expected: str = build_range_param(datetime(2024, 1, 1, tzinfo=UTC), aware_end)
        assert result == expected


class TestIntervalToSeconds:
    """Tests for interval_to_seconds() in tvkit.api.chart.utils."""

    @pytest.mark.parametrize(
        "interval,expected_seconds",
        [
            ("1S", 1),  # 1 second
            ("30S", 30),  # 30 seconds
            ("1", 60),  # 1 minute
            ("5", 300),  # 5 minutes
            ("15", 900),  # 15 minutes
            ("1H", 3600),  # 1 hour
            ("4H", 14400),  # 4 hours
            ("1D", 86400),  # 1 day
            ("D", 86400),  # bare "D" == "1D"
        ],
    )
    def test_valid_intervals(self, interval: str, expected_seconds: int) -> None:
        """Supported interval strings map to the correct duration in seconds."""
        assert interval_to_seconds(interval) == expected_seconds

    @pytest.mark.parametrize(
        "interval",
        ["M", "1M", "2M", "3M", "6M", "W", "1W", "2W", "3W"],
    )
    def test_monthly_and_weekly_raise_value_error(self, interval: str) -> None:
        """Monthly and weekly intervals raise ValueError — not supported by segmentation engine."""
        with pytest.raises(ValueError):
            interval_to_seconds(interval)

    def test_invalid_string_raises_value_error(self) -> None:
        """Unrecognised interval strings raise ValueError."""
        with pytest.raises(ValueError):
            interval_to_seconds("invalid")

    def test_non_string_raises_type_error(self) -> None:
        """Non-string input raises TypeError."""
        with pytest.raises(TypeError):
            interval_to_seconds(123)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "interval",
        [" 1H ", "\t1H\n"],
    )
    def test_interval_with_whitespace(self, interval: str) -> None:
        """Leading/trailing whitespace (spaces and tabs/newlines) is stripped before parsing."""
        assert interval_to_seconds(interval) == 3600

    def test_lowercase_interval_raises_value_error(self) -> None:
        """Lowercase interval strings (e.g. '1h') are rejected as invalid format."""
        with pytest.raises(ValueError):
            interval_to_seconds("1h")
