"""
Tests for the utils module, specifically for timestamp conversion functionality
and chart utility functions (to_unix_timestamp, build_range_param, validate_interval).
"""

from datetime import UTC, datetime

import pytest

from tvkit.api.chart.utils import build_range_param, to_unix_timestamp
from tvkit.api.utils import convert_timestamp_to_iso


class TestTimestampConversion:
    """Test cases for timestamp conversion functionality."""

    def test_convert_timestamp_to_iso_basic(self) -> None:
        """Test basic timestamp conversion to ISO format."""
        # Test with a known timestamp
        timestamp: float = 1753436820.0
        result: str = convert_timestamp_to_iso(timestamp)

        # Expected: 2025-07-25T09:47:00+00:00
        assert result == "2025-07-25T09:47:00+00:00"
        assert result.endswith("+00:00")  # UTC timezone
        assert "T" in result  # ISO format separator

    def test_convert_timestamp_to_iso_epoch(self) -> None:
        """Test conversion of epoch timestamp (0)."""
        timestamp: float = 0.0
        result: str = convert_timestamp_to_iso(timestamp)

        # Expected: 1970-01-01T00:00:00+00:00
        assert result == "1970-01-01T00:00:00+00:00"

    def test_convert_timestamp_to_iso_known_date(self) -> None:
        """Test conversion of a known date."""
        # January 1, 2022, 00:00:00 UTC
        timestamp: float = 1640995200.0
        result: str = convert_timestamp_to_iso(timestamp)

        # Expected: 2022-01-01T00:00:00+00:00
        assert result == "2022-01-01T00:00:00+00:00"

    def test_convert_timestamp_to_iso_fractional_seconds(self) -> None:
        """Test conversion with fractional seconds."""
        # Test with fractional seconds
        timestamp: float = 1640995200.5
        result: str = convert_timestamp_to_iso(timestamp)

        # Should handle fractional seconds
        assert result.startswith("2022-01-01T00:00:00")
        assert "+00:00" in result

    def test_convert_timestamp_to_iso_format_validation(self) -> None:
        """Test that the output format is valid ISO 8601."""
        timestamp: float = 1753436820.0
        result: str = convert_timestamp_to_iso(timestamp)

        # Validate ISO format components
        assert len(result) >= 19  # Minimum ISO format length
        assert result.count("T") == 1  # Date-time separator
        assert result.count("+") == 1  # Timezone offset
        assert result.count(":") >= 2  # Time separators
        assert result.count("-") >= 2  # Date separators

    def test_convert_timestamp_consistency(self) -> None:
        """Test that conversion is consistent and reversible."""
        timestamp: float = 1753436820.0
        iso_string: str = convert_timestamp_to_iso(timestamp)

        # Parse back to datetime and verify
        parsed_dt: datetime = datetime.fromisoformat(iso_string)
        back_to_timestamp: float = parsed_dt.timestamp()

        # Should be very close (within floating point precision)
        assert abs(back_to_timestamp - timestamp) < 0.001

    def test_convert_timestamp_timezone(self) -> None:
        """Test that the timezone is always UTC."""
        timestamps: list[float] = [0.0, 1640995200.0, 1753436820.0]

        for timestamp in timestamps:
            result: str = convert_timestamp_to_iso(timestamp)
            # All results should end with UTC timezone offset
            assert result.endswith("+00:00"), f"Timestamp {timestamp} should have UTC timezone"

    def test_convert_timestamp_type_validation(self) -> None:
        """Test that the function handles different numeric types."""
        # Test with int
        timestamp_int: int = 1640995200
        result_int: str = convert_timestamp_to_iso(float(timestamp_int))

        # Test with float
        timestamp_float: float = 1640995200.0
        result_float: str = convert_timestamp_to_iso(timestamp_float)

        # Results should be the same
        assert result_int == result_float


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
