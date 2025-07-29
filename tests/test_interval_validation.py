"""Tests for interval validation utility function."""

import pytest
from tvkit.api.chart.utils import validate_interval


class TestIntervalValidation:
    """Test cases for validate_interval function."""

    def test_valid_minute_intervals(self) -> None:
        """Test valid minute interval formats."""
        valid_minutes = ["1", "5", "15", "30", "45", "60", "120", "240", "480", "1440"]
        for interval in valid_minutes:
            validate_interval(interval)  # Should not raise

    def test_valid_second_intervals(self) -> None:
        """Test valid second interval formats."""
        valid_seconds = ["1S", "5S", "15S", "30S", "60S"]
        for interval in valid_seconds:
            validate_interval(interval)  # Should not raise

    def test_valid_hour_intervals(self) -> None:
        """Test valid hour interval formats."""
        valid_hours = ["1H", "2H", "3H", "4H", "6H", "8H", "12H", "24H"]
        for interval in valid_hours:
            validate_interval(interval)  # Should not raise

    def test_valid_day_intervals(self) -> None:
        """Test valid day interval formats."""
        valid_days = ["D", "1D", "2D", "3D", "7D"]
        for interval in valid_days:
            validate_interval(interval)  # Should not raise

    def test_valid_week_intervals(self) -> None:
        """Test valid week interval formats."""
        valid_weeks = ["W", "1W", "2W", "4W"]
        for interval in valid_weeks:
            validate_interval(interval)  # Should not raise

    def test_valid_month_intervals(self) -> None:
        """Test valid month interval formats."""
        valid_months = ["M", "1M", "2M", "3M", "6M", "12M"]
        for interval in valid_months:
            validate_interval(interval)  # Should not raise

    def test_invalid_empty_intervals(self) -> None:
        """Test invalid empty or whitespace intervals."""
        invalid_intervals = ["", "   ", "\t", "\n"]
        for interval in invalid_intervals:
            with pytest.raises(ValueError, match="Interval must be a non-empty string"):
                validate_interval(interval)

    def test_invalid_format_intervals(self) -> None:
        """Test invalid interval formats."""
        invalid_formats = ["1X", "H1", "D1", "M1", "W1", "invalid", "5m", "1h", "1d"]
        for interval in invalid_formats:
            with pytest.raises(ValueError, match="Invalid interval format"):
                validate_interval(interval)

    def test_invalid_minute_ranges(self) -> None:
        """Test invalid minute values outside acceptable range."""
        invalid_minutes = ["0", "-1", "1441", "9999"]
        for interval in invalid_minutes:
            with pytest.raises(ValueError):
                validate_interval(interval)

    def test_invalid_second_ranges(self) -> None:
        """Test invalid second values outside acceptable range."""
        invalid_seconds = ["0S", "61S", "3600S"]
        for interval in invalid_seconds:
            with pytest.raises(ValueError, match="Invalid second interval"):
                validate_interval(interval)

    def test_invalid_hour_ranges(self) -> None:
        """Test invalid hour values outside acceptable range."""
        invalid_hours = ["0H", "169H", "1000H"]
        for interval in invalid_hours:
            with pytest.raises(ValueError, match="Invalid hour interval"):
                validate_interval(interval)

    def test_invalid_day_ranges(self) -> None:
        """Test invalid day values outside acceptable range."""
        invalid_days = ["0D", "366D", "1000D"]
        for interval in invalid_days:
            with pytest.raises(ValueError, match="Invalid day interval"):
                validate_interval(interval)

    def test_invalid_week_ranges(self) -> None:
        """Test invalid week values outside acceptable range."""
        invalid_weeks = ["0W", "53W", "100W"]
        for interval in invalid_weeks:
            with pytest.raises(ValueError, match="Invalid week interval"):
                validate_interval(interval)

    def test_invalid_month_ranges(self) -> None:
        """Test invalid month values outside acceptable range."""
        invalid_months = ["0M", "13M", "100M"]
        for interval in invalid_months:
            with pytest.raises(ValueError, match="Invalid month interval"):
                validate_interval(interval)

    def test_edge_cases(self) -> None:
        """Test edge case intervals."""
        # Test maximum valid values
        validate_interval("1440")  # Max minutes (1 day)
        validate_interval("60S")  # Max seconds
        validate_interval("168H")  # Max hours (1 week)
        validate_interval("365D")  # Max days (1 year)
        validate_interval("52W")  # Max weeks (1 year)
        validate_interval("12M")  # Max months (1 year)

        # Test whitespace handling
        validate_interval(" 5 ")  # Should be trimmed and valid
        validate_interval("\t1H\t")  # Should be trimmed and valid
