# Chart Utils Documentation

## Overview

The `utils` module provides essential utility functions for TradingView chart API operations. It contains validation and helper functions that ensure data integrity and proper format compliance across all chart-related operations in tvkit.

**Module Path**: `tvkit.api.chart.utils`

## Architecture

The chart utils module serves as a foundational component providing:

- **Input Validation**: Ensures TradingView API parameter compliance
- **Format Standardization**: Validates interval formats across different timeframes
- **Error Prevention**: Catches invalid parameters before API calls
- **Type Safety**: Provides clear validation with descriptive error messages
- **Performance**: Lightweight validation with minimal overhead

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

**Minutes** (number only):
- `"1"`, `"5"`, `"15"`, `"30"`, `"45"`, `"60"`, `"120"`, `"180"`, `"240"`, etc.
- Range: 1-1440 minutes (up to 1 day)
- Common values: `"1"` (1min), `"5"` (5min), `"15"` (15min), `"30"` (30min)

**Seconds** (number + S):
- `"1S"`, `"5S"`, `"15S"`, `"30S"`
- Range: 1S-60S (up to 1 minute)
- Use cases: High-frequency trading, tick-level analysis

**Hours** (number + H):
- `"1H"`, `"2H"`, `"3H"`, `"4H"`, `"6H"`, `"8H"`, `"12H"`
- Range: 1H-168H (up to 1 week)
- Common values: `"1H"` (1 hour), `"4H"` (4 hours), `"12H"` (12 hours)

**Days** (D or number + D):
- `"D"`, `"1D"`, `"2D"`, `"3D"` (up to `"365D"`)
- Range: 1D-365D (up to 1 year)
- `"D"` is equivalent to `"1D"` (daily)

**Weeks** (W or number + W):
- `"W"`, `"1W"`, `"2W"`, `"3W"` (up to `"52W"`)
- Range: 1W-52W (up to 1 year)
- `"W"` is equivalent to `"1W"` (weekly)

**Months** (M or number + M):
- `"M"`, `"1M"`, `"2M"`, `"3M"`, `"6M"`, `"12M"`
- Range: 1M-12M (up to 1 year)
- `"M"` is equivalent to `"1M"` (monthly)

**Implementation Details**:

The function uses regex patterns for format validation:

```python
patterns = [
    r"^\d+$",        # Minutes: "1", "5", "15", "30", "45", "60"
    r"^\d+S$",       # Seconds: "1S", "5S", "15S", "30S"
    r"^\d+H$",       # Hours: "1H", "2H", "3H", "4H", "6H", "8H", "12H"
    r"^(\d+)?D$",    # Days: "D", "1D", "2D", "3D"
    r"^(\d+)?W$",    # Weeks: "W", "1W", "2W", "3W", "4W"
    r"^(\d+)?M$",    # Months: "M", "1M", "2M", "3M", "6M", "12M"
]
```

**Range Validation**:
- **Minutes**: 1-1440 (prevents intervals longer than 1 day)
- **Seconds**: 1-60 (prevents intervals longer than 1 minute)
- **Hours**: 1-168 (prevents intervals longer than 1 week)
- **Days**: 1-365 (prevents intervals longer than 1 year)
- **Weeks**: 1-52 (prevents intervals longer than 1 year)
- **Months**: 1-12 (prevents intervals longer than 1 year)

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

## Trading Strategy Applications

### Timeframe Analysis

```python
from tvkit.api.chart.utils import validate_interval

class TimeframeAnalyzer:
    """Analyze different timeframes for trading strategies"""

    def __init__(self):
        self.timeframes = {
            "scalping": ["1", "5", "15"],           # Short-term
            "day_trading": ["15", "30", "1H"],      # Intraday
            "swing_trading": ["4H", "D", "W"],      # Medium-term
            "position_trading": ["D", "W", "M"]     # Long-term
        }

    def validate_strategy_timeframes(self, strategy_type: str) -> bool:
        """Validate all timeframes for a trading strategy"""
        if strategy_type not in self.timeframes:
            return False

        intervals = self.timeframes[strategy_type]
        print(f"Validating {strategy_type} timeframes...")

        all_valid = True
        for interval in intervals:
            try:
                validate_interval(interval)
                print(f"  ✅ {interval}: Valid")
            except ValueError as e:
                print(f"  ❌ {interval}: Invalid - {e}")
                all_valid = False

        return all_valid

    def get_recommended_intervals(self, strategy_type: str) -> list[str]:
        """Get validated intervals for a strategy type"""
        if strategy_type not in self.timeframes:
            return []

        valid_intervals = []
        for interval in self.timeframes[strategy_type]:
            try:
                validate_interval(interval)
                valid_intervals.append(interval)
            except ValueError:
                pass  # Skip invalid intervals

        return valid_intervals

# Usage example
analyzer = TimeframeAnalyzer()

for strategy in ["scalping", "day_trading", "swing_trading", "position_trading"]:
    print(f"\n📊 {strategy.replace('_', ' ').title()} Strategy:")
    is_valid = analyzer.validate_strategy_timeframes(strategy)
    recommended = analyzer.get_recommended_intervals(strategy)
    print(f"   Status: {'✅ All Valid' if is_valid else '⚠️  Some Invalid'}")
    print(f"   Recommended: {', '.join(recommended)}")
```

### Multi-Timeframe Data Collection

```python
async def collect_multi_timeframe_data(symbol: str, timeframes: list[str]):
    """
    Collect data across multiple validated timeframes

    Args:
        symbol: Trading symbol (e.g., "NASDAQ:AAPL")
        timeframes: List of interval strings
    """
    from tvkit.api.chart.ohlcv import OHLCV

    # Validate all timeframes first
    valid_timeframes = []
    print(f"Validating timeframes for {symbol}...")

    for timeframe in timeframes:
        try:
            validate_interval(timeframe)
            valid_timeframes.append(timeframe)
            print(f"  ✅ {timeframe}: Valid")
        except ValueError as e:
            print(f"  ❌ {timeframe}: Invalid - {e}")

    if not valid_timeframes:
        print("❌ No valid timeframes found!")
        return {}

    # Collect data for valid timeframes
    results = {}
    async with OHLCV() as client:
        for timeframe in valid_timeframes:
            try:
                print(f"\n📊 Fetching {symbol} data for {timeframe} interval...")
                bars = await client.get_historical_ohlcv(
                    symbol,
                    interval=timeframe,
                    bars_count=20
                )

                results[timeframe] = {
                    "bars_count": len(bars),
                    "latest_price": bars[-1].close if bars else None,
                    "price_range": (min(bar.close for bar in bars),
                                  max(bar.close for bar in bars)) if bars else None
                }

                print(f"  ✅ Collected {len(bars)} bars")
                if bars:
                    print(f"  💰 Latest price: ${bars[-1].close:.2f}")

            except Exception as e:
                print(f"  ❌ Failed to fetch {timeframe} data: {e}")
                results[timeframe] = {"error": str(e)}

    return results

# Example usage
async def multi_timeframe_analysis():
    symbol = "NASDAQ:AAPL"
    timeframes = ["1", "5", "15", "1H", "4H", "D", "W", "invalid_interval"]

    results = await collect_multi_timeframe_data(symbol, timeframes)

    print(f"\n📈 Multi-timeframe Analysis Results for {symbol}:")
    print("-" * 60)

    for timeframe, data in results.items():
        if "error" in data:
            print(f"❌ {timeframe}: {data['error']}")
        else:
            print(f"✅ {timeframe}: {data['bars_count']} bars, "
                  f"Latest: ${data['latest_price']:.2f}")

# Run the analysis
import asyncio
asyncio.run(multi_timeframe_analysis())
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

## Performance Considerations

### Validation Overhead

The `validate_interval()` function is designed for minimal performance impact:

**Time Complexity**: O(1) - Constant time validation using regex patterns
**Space Complexity**: O(1) - No additional memory allocation
**Typical Execution Time**: < 0.01ms per validation

### Optimization for High-Frequency Usage

```python
class IntervalValidator:
    """Cached interval validator for high-frequency usage"""

    def __init__(self):
        self._cache = {}  # Cache validation results
        self._cache_hits = 0
        self._cache_misses = 0

    def validate(self, interval: str) -> bool:
        """Validate interval with caching for performance"""
        if interval in self._cache:
            self._cache_hits += 1
            result = self._cache[interval]
            if not result["valid"]:
                raise ValueError(result["error"])
            return True

        self._cache_misses += 1

        try:
            validate_interval(interval)
            self._cache[interval] = {"valid": True, "error": None}
            return True
        except ValueError as e:
            self._cache[interval] = {"valid": False, "error": str(e)}
            raise

    def get_cache_stats(self) -> dict:
        """Get cache performance statistics"""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate_percent": hit_rate,
            "cached_intervals": len(self._cache)
        }

# Performance testing
import time

def performance_test():
    """Test validation performance with and without caching"""
    intervals = ["1", "5", "15", "1H", "4H", "D"] * 1000  # 6000 validations

    # Test without caching
    start_time = time.time()
    for interval in intervals:
        try:
            validate_interval(interval)
        except ValueError:
            pass
    no_cache_time = time.time() - start_time

    # Test with caching
    validator = IntervalValidator()
    start_time = time.time()
    for interval in intervals:
        try:
            validator.validate(interval)
        except ValueError:
            pass
    cache_time = time.time() - start_time

    # Results
    stats = validator.get_cache_stats()
    print(f"Performance Comparison ({len(intervals)} validations):")
    print(f"  Without caching: {no_cache_time:.4f}s")
    print(f"  With caching: {cache_time:.4f}s")
    print(f"  Performance improvement: {((no_cache_time - cache_time) / no_cache_time * 100):.1f}%")
    print(f"  Cache hit rate: {stats['hit_rate_percent']:.1f}%")

# Run performance test
performance_test()
```

## Integration Examples

### With OHLCV Client Validation

```python
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.chart.utils import validate_interval

class ValidatedOHLCVClient:
    """OHLCV client wrapper with automatic interval validation"""

    def __init__(self):
        self.client = None

    async def __aenter__(self):
        self.client = OHLCV()
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def get_validated_ohlcv(self, symbol: str, interval: str, bars_count: int = 10):
        """Get OHLCV data with automatic interval validation"""
        # Validate interval before API call
        try:
            validate_interval(interval)
        except ValueError as e:
            raise ValueError(f"Invalid interval '{interval}' for symbol {symbol}: {e}")

        # Proceed with validated interval
        async for bar in self.client.get_ohlcv(symbol, interval, bars_count):
            yield bar

# Usage with validation
async def safe_data_streaming():
    async with ValidatedOHLCVClient() as client:
        try:
            # This will validate the interval first
            async for bar in client.get_validated_ohlcv("NASDAQ:AAPL", "5", 10):
                print(f"AAPL: ${bar.close}")
                break
        except ValueError as e:
            print(f"Validation error: {e}")

asyncio.run(safe_data_streaming())
```

## API Reference Summary

### Functions

**validate_interval(interval: str) -> None**
- Validates TradingView interval format
- Supports minutes, seconds, hours, days, weeks, months
- Raises ValueError for invalid formats or ranges

### Supported Formats

**Minutes**: `"1"`, `"5"`, `"15"`, `"30"`, `"60"`, etc. (1-1440)
**Seconds**: `"1S"`, `"5S"`, `"15S"`, `"30S"` (1S-60S)
**Hours**: `"1H"`, `"2H"`, `"4H"`, `"12H"` (1H-168H)
**Days**: `"D"`, `"1D"`, `"2D"`, `"7D"` (1D-365D)
**Weeks**: `"W"`, `"1W"`, `"2W"`, `"4W"` (1W-52W)
**Months**: `"M"`, `"1M"`, `"3M"`, `"6M"` (1M-12M)

### Error Types

**ValueError**: Raised for:
- Invalid format patterns
- Out-of-range values
- Empty or null intervals
- Unsupported timeframe combinations

## Related Components

**Core Dependencies**:
- `re`: Regular expression pattern matching for format validation
- Built-in Python types for range validation

**Integration Points**:
- **OHLCV Client**: Uses `validate_interval()` for parameter validation
- **ConnectionService**: Relies on validated intervals for chart requests
- **MessageService**: Passes validated intervals in protocol messages

---

**Note**: This documentation reflects tvkit v0.1.4. The utils module provides essential validation functions used throughout the chart API components to ensure data integrity and TradingView API compliance.