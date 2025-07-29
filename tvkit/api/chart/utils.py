"""Utility functions for chart API operations."""

import re


def validate_interval(interval: str) -> None:
    """
    Validates TradingView interval format.

    Supports TradingView interval formats:
    - Minutes: "1", "5", "15", "30", "45" (number only)
    - Seconds: "1S", "5S", "15S", "30S" (number + S)
    - Hours: "1H", "2H", "3H", "4H", "6H", "8H", "12H" (number + H)
    - Days: "D", "1D", "2D", "3D" (D or number + D)
    - Weeks: "W", "1W", "2W", "3W" (W or number + W)
    - Months: "M", "1M", "2M", "3M", "6M" (M or number + M)

    Args:
        interval: The interval string to validate

    Raises:
        ValueError: If interval format is invalid

    Example:
        >>> validate_interval("5")     # 5 minutes - valid
        >>> validate_interval("1H")    # 1 hour - valid
        >>> validate_interval("D")     # Daily - valid
        >>> validate_interval("15S")   # 15 seconds - valid
        >>> validate_interval("2W")    # 2 weeks - valid
        >>> validate_interval("invalid")  # Raises ValueError
    """
    if not interval.strip():
        raise ValueError("Interval must be a non-empty string")

    interval = interval.strip()

    # Pattern for TradingView interval formats
    # Minutes: just numbers (1, 5, 15, 30, 45, 60, 120, 180, 240, 360, 480, 720, 1440)
    # Seconds: number + S (1S, 5S, 15S, 30S)
    # Hours: number + H (1H, 2H, 3H, 4H, 6H, 8H, 12H)
    # Days: D or number + D (D, 1D, 2D, 3D)
    # Weeks: W or number + W (W, 1W, 2W, 3W, 4W)
    # Months: M or number + M (M, 1M, 2M, 3M, 6M, 12M)

    patterns: list[str] = [
        r"^\d+$",  # Minutes: "1", "5", "15", "30", "45", "60", etc.
        r"^\d+S$",  # Seconds: "1S", "5S", "15S", "30S"
        r"^\d+H$",  # Hours: "1H", "2H", "3H", "4H", "6H", "8H", "12H"
        r"^(\d+)?D$",  # Days: "D", "1D", "2D", "3D"
        r"^(\d+)?W$",  # Weeks: "W", "1W", "2W", "3W", "4W"
        r"^(\d+)?M$",  # Months: "M", "1M", "2M", "3M", "6M", "12M"
    ]

    for pattern in patterns:
        if re.match(pattern, interval):
            # Additional validation for reasonable ranges
            if interval.isdigit():
                # Minutes validation
                minutes: int = int(interval)
                if (
                    minutes <= 0 or minutes > 1440
                ):  # Max 1 day in minutes (common limit)
                    raise ValueError(
                        f"Invalid minute interval: {interval}. Must be between 1 and 1440 minutes"
                    )
            elif interval.endswith("S"):
                # Seconds validation
                seconds: int = int(interval[:-1])
                if seconds <= 0 or seconds > 60:  # Max 60 seconds
                    raise ValueError(
                        f"Invalid second interval: {interval}. Must be between 1S and 60S"
                    )
            elif interval.endswith("H"):
                # Hours validation
                hours: int = int(interval[:-1])
                if hours <= 0 or hours > 168:  # Max 1 week in hours
                    raise ValueError(
                        f"Invalid hour interval: {interval}. Must be between 1H and 168H"
                    )
            elif interval.endswith("D"):
                # Days validation
                if interval == "D":
                    return  # Valid
                days: int = int(interval[:-1])
                if days <= 0 or days > 365:  # Max 1 year in days
                    raise ValueError(
                        f"Invalid day interval: {interval}. Must be between 1D and 365D"
                    )
            elif interval.endswith("W"):
                # Weeks validation
                if interval == "W":
                    return  # Valid
                weeks: int = int(interval[:-1])
                if weeks <= 0 or weeks > 52:  # Max 1 year in weeks
                    raise ValueError(
                        f"Invalid week interval: {interval}. Must be between 1W and 52W"
                    )
            elif interval.endswith("M"):
                # Months validation
                if interval == "M":
                    return  # Valid
                months: int = int(interval[:-1])
                if months <= 0 or months > 12:  # Max 1 year in months
                    raise ValueError(
                        f"Invalid month interval: {interval}. Must be between 1M and 12M"
                    )
            return  # Valid interval

    raise ValueError(
        f"Invalid interval format: '{interval}'. "
        f"Expected formats: minutes (1, 5, 15), seconds (15S), hours (1H), "
        f"days (D, 1D), weeks (W, 1W), months (M, 1M)"
    )
