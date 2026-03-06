# Chart Utils Documentation

## Overview

The `utils` module provides essential utility functions for TradingView chart API operations. It contains validation and helper functions that ensure data integrity and proper format compliance across all chart-related operations in tvkit.

**Module Path**: `tvkit.api.chart.utils`

## Quick Reference

```python
from tvkit.api.chart.utils import (
    validate_interval,
    build_range_param,
    to_unix_timestamp,
    MAX_BARS_REQUEST,
)

# Validate an interval before using it
validate_interval("1D")

# Build a date-range parameter for get_historical_ohlcv()
build_range_param("2024-01-01", "2024-12-31")
# → "r,1704067200:1735603200"

# Convert a datetime or ISO string to Unix timestamp
to_unix_timestamp("2024-01-01")
# → 1704067200
```

## Architecture

The utils module provides helper functions used by the chart API: interval validation for all OHLCV methods, and date-range utilities used by `get_historical_ohlcv()` range mode.

## Functions

### Interval Validation

#### validate_interval()

```python
def validate_interval(interval: str) -> None
```

**Description**: Validates TradingView interval format to ensure compatibility with the WebSocket API.

**Parameters**:
- `interval` (str): The interval string to validate

**Returns**: None (raises exception for invalid intervals)

**Raises**:
- `ValueError`: If interval format is invalid or out of acceptable range

**Supported Interval Formats**:

| Unit | Format | Examples |
| --- | --- | --- |
| Minutes | number | `"1"`, `"5"`, `"15"`, `"30"`, `"60"`, `"240"` |
| Seconds | number + S | `"1S"`, `"5S"`, `"15S"`, `"30S"` |
| Hours | number + H | `"1H"`, `"2H"`, `"4H"`, `"12H"` |
| Days | D or number + D | `"D"`, `"1D"`, `"2D"`, `"7D"` |
| Weeks | W or number + W | `"W"`, `"1W"`, `"2W"`, `"4W"` |
| Months | M or number + M | `"M"`, `"1M"`, `"3M"`, `"6M"`, `"12M"` |

**Typical numeric ranges** (may vary by exchange and account tier):

- **Minutes**: 1–1440
- **Seconds**: 1–60
- **Hours**: 1–168
- **Days**: 1–365
- **Weeks**: 1–52
- **Months**: 1–12

Range validation occurs after format validation. The implementation uses regular expressions to check the format, then validates the numeric component against the ranges above.

## Usage Examples

### Basic Interval Validation

```python
from tvkit.api.chart.utils import validate_interval

# Valid minute intervals
validate_interval("1")      # 1 minute ✅
validate_interval("5")      # 5 minutes ✅
validate_interval("15")     # 15 minutes ✅
validate_interval("30")     # 30 minutes ✅
validate_interval("60")     # 1 hour (in minutes) ✅

# Valid second intervals
validate_interval("1S")     # 1 second ✅
validate_interval("5S")     # 5 seconds ✅
validate_interval("15S")    # 15 seconds ✅
validate_interval("30S")    # 30 seconds ✅

# Valid hour intervals
validate_interval("1H")     # 1 hour ✅
validate_interval("2H")     # 2 hours ✅
validate_interval("4H")     # 4 hours ✅
validate_interval("12H")    # 12 hours ✅

# Valid day intervals
validate_interval("D")      # Daily (equivalent to 1D) ✅
validate_interval("1D")     # 1 day ✅
validate_interval("2D")     # 2 days ✅
validate_interval("7D")     # 1 week (in days) ✅

# Valid week intervals
validate_interval("W")      # Weekly (equivalent to 1W) ✅
validate_interval("1W")     # 1 week ✅
validate_interval("2W")     # 2 weeks ✅
validate_interval("4W")     # 4 weeks ✅

# Valid month intervals
validate_interval("M")      # Monthly (equivalent to 1M) ✅
validate_interval("1M")     # 1 month ✅
validate_interval("3M")     # 3 months ✅
validate_interval("6M")     # 6 months ✅
```

### Error Handling Examples

```python
from tvkit.api.chart.utils import validate_interval

# Invalid formats - will raise ValueError
try:
    validate_interval("invalid")    # Invalid format
except ValueError as e:
    print(f"Error: {e}")
    # Error: Invalid interval format: 'invalid'. Expected formats...

try:
    validate_interval("1.5")        # Decimal not supported
except ValueError as e:
    print(f"Error: {e}")

try:
    validate_interval("0")          # Zero not allowed
except ValueError as e:
    print(f"Error: {e}")
    # Error: Invalid minute interval: 0. Must be between 1 and 1440 minutes

try:
    validate_interval("2000")       # Exceeds maximum minutes
except ValueError as e:
    print(f"Error: {e}")
    # Error: Invalid minute interval: 2000. Must be between 1 and 1440 minutes

try:
    validate_interval("25H")        # Exceeds maximum hours
except ValueError as e:
    print(f"Error: {e}")
    # Error: Invalid hour interval: 25H. Must be between 1H and 168H

try:
    validate_interval("")           # Empty string
except ValueError as e:
    print(f"Error: {e}")
    # Error: Interval must be a non-empty string
```

### Integration with OHLCV Client

```python
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.chart.utils import validate_interval

async def safe_data_streaming():
    intervals_to_test = [
        "1",     # 1 minute
        "5",     # 5 minutes
        "15",    # 15 minutes
        "1H",    # 1 hour
        "4H",    # 4 hours
        "D",     # Daily
        "W",     # Weekly
        "M"      # Monthly
    ]

    for interval in intervals_to_test:
        try:
            # Validate before using
            validate_interval(interval)
            print(f"✅ {interval} is valid")

            # Use with OHLCV client
            async with OHLCV() as client:
                bars = await client.get_historical_ohlcv(
                    "NASDAQ:AAPL",
                    interval=interval,
                    bars_count=10
                )
                print(f"   Fetched {len(bars)} bars for {interval} interval")

        except ValueError as e:
            print(f"❌ {interval} is invalid: {e}")
        except Exception as e:
            print(f"⚠️  Error fetching data for {interval}: {e}")

# Run the validation test
import asyncio
asyncio.run(safe_data_streaming())
```

### Bulk Interval Validation

```python
def validate_multiple_intervals(intervals: list[str]) -> dict[str, bool]:
    """
    Validate multiple intervals and return results.

    Args:
        intervals: List of interval strings to validate

    Returns:
        Dictionary mapping intervals to validation results
    """
    results = {}

    for interval in intervals:
        try:
            validate_interval(interval)
            results[interval] = True
            print(f"✅ {interval}: Valid")
        except ValueError as e:
            results[interval] = False
            print(f"❌ {interval}: Invalid - {e}")

    return results

# Test various intervals
test_intervals = [
    # Valid intervals
    "1", "5", "15", "30", "1H", "4H", "D", "1D", "W", "1W", "M", "1M",
    # Invalid intervals
    "0", "invalid", "1.5", "2000", "25H", "400D", "100W", "50M"
]

print("Validating multiple intervals:")
validation_results = validate_multiple_intervals(test_intervals)

# Summary
valid_count = sum(validation_results.values())
total_count = len(validation_results)
print(f"\nSummary: {valid_count}/{total_count} intervals are valid")
```

## Error Handling Patterns

### Graceful Validation with Fallbacks

```python
def validate_interval_with_fallback(interval: str, fallback: str = "1") -> str:
    """
    Validate interval with fallback to default if invalid

    Args:
        interval: Preferred interval
        fallback: Fallback interval if preferred is invalid

    Returns:
        Valid interval string (either preferred or fallback)
    """
    try:
        validate_interval(interval)
        return interval
    except ValueError as e:
        print(f"⚠️  Invalid interval '{interval}': {e}")

        try:
            validate_interval(fallback)
            print(f"🔄 Using fallback interval: {fallback}")
            return fallback
        except ValueError:
            print(f"❌ Fallback interval '{fallback}' is also invalid!")
            return "1"  # Ultimate fallback to 1 minute

# Usage examples
test_intervals = ["invalid", "0", "5", "25H", "1H"]

for interval in test_intervals:
    validated = validate_interval_with_fallback(interval, fallback="15")
    print(f"Input: {interval} → Output: {validated}\n")
```

### Comprehensive Validation Function

```python
def comprehensive_interval_check(interval: str) -> dict[str, any]:
    """
    Comprehensive interval validation with detailed feedback

    Args:
        interval: Interval string to validate

    Returns:
        Dictionary with validation results and metadata
    """
    result = {
        "original": interval,
        "is_valid": False,
        "error_message": None,
        "category": None,
        "numeric_value": None,
        "time_unit": None,
        "equivalent_minutes": None
    }

    try:
        validate_interval(interval)
        result["is_valid"] = True

        # Determine category and extract components
        if interval.isdigit():
            result["category"] = "minutes"
            result["numeric_value"] = int(interval)
            result["time_unit"] = "minutes"
            result["equivalent_minutes"] = int(interval)

        elif interval.endswith("S"):
            result["category"] = "seconds"
            result["numeric_value"] = int(interval[:-1])
            result["time_unit"] = "seconds"
            result["equivalent_minutes"] = int(interval[:-1]) / 60

        elif interval.endswith("H"):
            result["category"] = "hours"
            result["numeric_value"] = int(interval[:-1])
            result["time_unit"] = "hours"
            result["equivalent_minutes"] = int(interval[:-1]) * 60

        elif interval.endswith("D"):
            result["category"] = "days"
            result["numeric_value"] = 1 if interval == "D" else int(interval[:-1])
            result["time_unit"] = "days"
            result["equivalent_minutes"] = result["numeric_value"] * 24 * 60

        elif interval.endswith("W"):
            result["category"] = "weeks"
            result["numeric_value"] = 1 if interval == "W" else int(interval[:-1])
            result["time_unit"] = "weeks"
            result["equivalent_minutes"] = result["numeric_value"] * 7 * 24 * 60

        elif interval.endswith("M"):
            result["category"] = "months"
            result["numeric_value"] = 1 if interval == "M" else int(interval[:-1])
            result["time_unit"] = "months"
            result["equivalent_minutes"] = result["numeric_value"] * 30 * 24 * 60  # Approximate

    except ValueError as e:
        result["error_message"] = str(e)

    return result

# Test comprehensive validation
test_cases = ["1", "5", "15S", "1H", "4H", "D", "1D", "W", "2W", "M", "3M", "invalid", "0", "25H"]

print("Comprehensive Interval Analysis:")
print("=" * 80)

for interval in test_cases:
    analysis = comprehensive_interval_check(interval)

    status = "✅ Valid" if analysis["is_valid"] else "❌ Invalid"
    print(f"\nInterval: '{interval}' - {status}")

    if analysis["is_valid"]:
        print(f"  Category: {analysis['category']}")
        print(f"  Value: {analysis['numeric_value']} {analysis['time_unit']}")
        print(f"  Equivalent minutes: {analysis['equivalent_minutes']:.2f}")
    else:
        print(f"  Error: {analysis['error_message']}")
```

## Date Range Utilities

New in the historical OHLCV date-range feature. These symbols are exported from `tvkit.api.chart.utils` alongside `validate_interval`.

### MAX_BARS_REQUEST

```python
MAX_BARS_REQUEST: int = 5000
```

**Purpose**: Fills the required `bars_count` parameter slot in the `create_series` WebSocket message during range mode. The TradingView protocol requires a value in this slot — `MAX_BARS_REQUEST` satisfies the protocol requirement. The server ignores this value once a `modify_series` date-range constraint is applied.

**Value**: `5000`

**Account-tier note**: Free TradingView accounts may receive fewer bars than this limit; paid accounts may receive more.

**Usage**:

```python
from tvkit.api.chart.utils import MAX_BARS_REQUEST

# Used internally by get_historical_ohlcv() in range mode.
# You will not normally need to use this constant directly.
print(MAX_BARS_REQUEST)  # 5000
```

---

### to_unix_timestamp()

```python
def to_unix_timestamp(ts: datetime | str) -> int
```

**Description**: Convert a `datetime` object or ISO 8601 string to a UTC Unix timestamp (integer seconds).

**Parameters**:

- `ts` (datetime | str): Input value to convert

**Returns**: `int` — Unix timestamp in UTC seconds since epoch. Microseconds are truncated (not rounded).

**Accepted input types**:

| Input type | Behaviour |
| --- | --- |
| Timezone-aware `datetime` | Converted to UTC, returned as integer seconds |
| Naive `datetime` (no tzinfo) | Assumed UTC; `logger.debug()` emitted — no exception |
| ISO 8601 date string (`"2024-01-01"`) | Parsed as UTC midnight |
| ISO 8601 datetime with offset (`"2024-01-01T12:00:00+05:30"`) | Converted to UTC |
| ISO 8601 with `"Z"` suffix (`"2024-01-01T00:00:00Z"`) | `"Z"` normalised to `"+00:00"` before parsing |

**Raises**:

- `ValueError`: If a string cannot be parsed as ISO 8601
- `TypeError`: If the input is not a `datetime` or `str`

**Examples**:

```python
from datetime import datetime, timezone
from tvkit.api.chart.utils import to_unix_timestamp

# Timezone-aware datetime
to_unix_timestamp(datetime(2024, 1, 1, tzinfo=timezone.utc))
# → 1704067200

# ISO date-only string (UTC midnight)
to_unix_timestamp("2024-01-01")
# → 1704067200

# ISO datetime with "Z" suffix
to_unix_timestamp("2024-06-15T09:30:00Z")
# → 1718443800

# ISO datetime with timezone offset
to_unix_timestamp("2024-01-01T05:30:00+05:30")
# → 1704067200  (same UTC moment as midnight UTC)
```

---

### build_range_param()

```python
def build_range_param(start: datetime | str, end: datetime | str) -> str
```

**Description**: Build the TradingView `modify_series` range parameter string from start and end timestamps.

**Parameters**:

- `start` (datetime | str): Start of the range, inclusive. Same accepted types as `to_unix_timestamp()`.
- `end` (datetime | str): End of the range, inclusive. Same accepted types as `to_unix_timestamp()`.

**Returns**: `str` — Range string in the format `"r,<from_unix>:<to_unix>"` (e.g., `"r,1704067200:1735603200"`).

**Validation rules**:

- `start > end` → raises `ValueError` (fail-fast before WebSocket connection opens)
- `start == end` → **valid** — fetches all intraday bars within that calendar day for the specified interval
- Type checking and conversion delegated to `to_unix_timestamp()`

**Raises**:

- `ValueError`: If `start` is after `end`, or if either value is an invalid ISO string
- `TypeError`: If either value is not a `datetime` or `str`

**Examples**:

```python
from datetime import datetime, timezone
from tvkit.api.chart.utils import build_range_param

# Full-year range
build_range_param("2024-01-01", "2024-12-31")
# → "r,1704067200:1735603200"

# Single-day (start == end is valid)
build_range_param("2024-06-15", "2024-06-15")
# → "r,1718409600:1718409600"

# Timezone-aware string inputs
build_range_param("2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z")
# → "r,1704067200:1706745599"

# Mixed datetime object and string
build_range_param(
    datetime(2024, 1, 1, tzinfo=timezone.utc),
    "2024-12-31",
)
# → "r,1704067200:1735603200"

# Invalid: start after end raises ValueError
build_range_param("2024-12-31", "2024-01-01")
# → raises ValueError: "start must be <= end"
```

---

## API Reference Summary

### Functions

`validate_interval(interval: str) -> None` — Validates TradingView interval format; supports minutes, seconds, hours, days, weeks, months; raises `ValueError` for invalid formats or out-of-range values.

`to_unix_timestamp(ts: datetime | str) -> int` — Converts datetime or ISO 8601 string to UTC Unix timestamp (integer seconds); naive datetimes treated as UTC (debug log emitted); raises `ValueError` for invalid strings, `TypeError` for wrong input type.

`build_range_param(start: datetime | str, end: datetime | str) -> str` — Builds TradingView range parameter string `"r,<from>:<to>"`; `start > end` raises `ValueError`; `start == end` is valid (single-day intraday fetch); used internally by `get_historical_ohlcv()` in range mode.

### Constants

`MAX_BARS_REQUEST: int = 5000` — Sentinel value used in `create_series` during range mode; satisfies the protocol parameter slot; ignored by TradingView server when range is active.

### Error Types

`ValueError` — Raised for invalid format patterns, out-of-range values, empty intervals, and `start > end`.

`TypeError` — Raised by `to_unix_timestamp()` and `build_range_param()` for non-datetime/str inputs.

## Related Components

**Integration Points**:

- **OHLCV Client**: Uses `validate_interval()` for all interval parameters; uses `build_range_param()` and `MAX_BARS_REQUEST` in range mode
- **ConnectionService**: Relies on validated intervals for chart series requests
- **MessageService**: Passes validated intervals in protocol messages

---

**Note**: This documentation reflects tvkit v0.1.5 (unreleased). The utils module provides validation and date-range helper functions used throughout the chart API components.
