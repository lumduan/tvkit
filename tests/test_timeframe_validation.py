"""Tests for timeframe validation utility function."""

import pytest
from tvkit.api.chart.utils import validate_timeframe


class TestTimeframeValidation:
    """Test cases for validate_timeframe function."""

    def test_valid_minute_timeframes(self) -> None:
        """Test valid minute timeframe formats."""
        valid_minutes = ["1", "5", "15", "30", "45", "60", "120", "240", "480", "1440"]
        for timeframe in valid_minutes:
            validate_timeframe(timeframe)  # Should not raise

    def test_valid_second_timeframes(self) -> None:
        """Test valid second timeframe formats."""
        valid_seconds = ["1S", "5S", "15S", "30S", "60S"]
        for timeframe in valid_seconds:
            validate_timeframe(timeframe)  # Should not raise

    def test_valid_hour_timeframes(self) -> None:
        """Test valid hour timeframe formats."""
        valid_hours = ["1H", "2H", "3H", "4H", "6H", "8H", "12H", "24H"]
        for timeframe in valid_hours:
            validate_timeframe(timeframe)  # Should not raise

    def test_valid_day_timeframes(self) -> None:
        """Test valid day timeframe formats."""
        valid_days = ["D", "1D", "2D", "3D", "7D"]
        for timeframe in valid_days:
            validate_timeframe(timeframe)  # Should not raise

    def test_valid_week_timeframes(self) -> None:
        """Test valid week timeframe formats."""
        valid_weeks = ["W", "1W", "2W", "4W"]
        for timeframe in valid_weeks:
            validate_timeframe(timeframe)  # Should not raise

    def test_valid_month_timeframes(self) -> None:
        """Test valid month timeframe formats."""
        valid_months = ["M", "1M", "2M", "3M", "6M", "12M"]
        for timeframe in valid_months:
            validate_timeframe(timeframe)  # Should not raise

    def test_invalid_empty_timeframes(self) -> None:
        """Test invalid empty or whitespace timeframes."""
        invalid_timeframes = ["", "   ", "\t", "\n"]
        for timeframe in invalid_timeframes:
            with pytest.raises(
                ValueError, match="Timeframe must be a non-empty string"
            ):
                validate_timeframe(timeframe)

    def test_invalid_format_timeframes(self) -> None:
        """Test invalid timeframe formats."""
        invalid_formats = ["1X", "H1", "D1", "M1", "W1", "invalid", "5m", "1h", "1d"]
        for timeframe in invalid_formats:
            with pytest.raises(ValueError, match="Invalid timeframe format"):
                validate_timeframe(timeframe)

    def test_invalid_minute_ranges(self) -> None:
        """Test invalid minute values outside acceptable range."""
        invalid_minutes = ["0", "-1", "1441", "9999"]
        for timeframe in invalid_minutes:
            with pytest.raises(ValueError):
                validate_timeframe(timeframe)

    def test_invalid_second_ranges(self) -> None:
        """Test invalid second values outside acceptable range."""
        invalid_seconds = ["0S", "61S", "3600S"]
        for timeframe in invalid_seconds:
            with pytest.raises(ValueError, match="Invalid second timeframe"):
                validate_timeframe(timeframe)

    def test_invalid_hour_ranges(self) -> None:
        """Test invalid hour values outside acceptable range."""
        invalid_hours = ["0H", "169H", "1000H"]
        for timeframe in invalid_hours:
            with pytest.raises(ValueError, match="Invalid hour timeframe"):
                validate_timeframe(timeframe)

    def test_invalid_day_ranges(self) -> None:
        """Test invalid day values outside acceptable range."""
        invalid_days = ["0D", "366D", "1000D"]
        for timeframe in invalid_days:
            with pytest.raises(ValueError, match="Invalid day timeframe"):
                validate_timeframe(timeframe)

    def test_invalid_week_ranges(self) -> None:
        """Test invalid week values outside acceptable range."""
        invalid_weeks = ["0W", "53W", "100W"]
        for timeframe in invalid_weeks:
            with pytest.raises(ValueError, match="Invalid week timeframe"):
                validate_timeframe(timeframe)

    def test_invalid_month_ranges(self) -> None:
        """Test invalid month values outside acceptable range."""
        invalid_months = ["0M", "13M", "100M"]
        for timeframe in invalid_months:
            with pytest.raises(ValueError, match="Invalid month timeframe"):
                validate_timeframe(timeframe)

    def test_edge_cases(self) -> None:
        """Test edge case timeframes."""
        # Test maximum valid values
        validate_timeframe("1440")  # Max minutes (1 day)
        validate_timeframe("60S")  # Max seconds
        validate_timeframe("168H")  # Max hours (1 week)
        validate_timeframe("365D")  # Max days (1 year)
        validate_timeframe("52W")  # Max weeks (1 year)
        validate_timeframe("12M")  # Max months (1 year)

        # Test whitespace handling
        validate_timeframe(" 5 ")  # Should be trimmed and valid
        validate_timeframe("\t1H\t")  # Should be trimmed and valid
