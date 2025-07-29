"""
Tests for the utils module, specifically for timestamp conversion functionality.
"""

from datetime import datetime

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
            assert result.endswith("+00:00"), (
                f"Timestamp {timestamp} should have UTC timezone"
            )

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
