# tvkit.api.utils

## Overview

The `tvkit.api.utils` module provides essential utility functions for the tvkit TradingView API library. This module centralizes common operations including timestamp conversion, symbol validation, and TradingView indicator calculations. It serves as a foundational layer supporting both the chart API and scanner API components with standardized data processing and validation capabilities.

## Architecture

The module is designed with a functional programming approach, providing stateless utility functions that can be safely used across the entire tvkit ecosystem. Each function is focused on a specific task with clear input/output contracts and comprehensive error handling.

### Key Components

- **Timestamp Utilities**: Convert between Unix timestamps and ISO 8601 format
- **Symbol Validation**: Async validation of trading symbols against TradingView API
- **TradingView Indicators**: Built-in technical analysis indicators with Pydantic models
- **Data Processing**: Helper functions for financial data manipulation

## Functions

### convert_timestamp_to_iso

```python
def convert_timestamp_to_iso(timestamp: int) -> str
```

Converts a Unix timestamp to ISO 8601 formatted string.

**Parameters:**
- `timestamp` (int): Unix timestamp in seconds

**Returns:**
- `str`: ISO 8601 formatted timestamp string (YYYY-MM-DDTHH:MM:SSZ)

**Raises:**
- `ValueError`: If timestamp is invalid or out of range
- `OSError`: If system cannot handle the timestamp conversion

**Example:**
```python
from tvkit.api.utils import convert_timestamp_to_iso

# Convert Unix timestamp to ISO format
timestamp = 1640995200  # January 1, 2022 00:00:00 UTC
iso_time = convert_timestamp_to_iso(timestamp)
print(iso_time)  # "2022-01-01T00:00:00Z"

# Handle current time
import time
current_timestamp = int(time.time())
current_iso = convert_timestamp_to_iso(current_timestamp)
print(f"Current time: {current_iso}")
```

### validate_symbols

```python
async def validate_symbols(symbols: List[str]) -> Dict[str, bool]
```

Asynchronously validates a list of trading symbols against TradingView's API to ensure they exist and are tradeable.

**Parameters:**
- `symbols` (List[str]): List of symbol strings to validate (e.g., ["AAPL", "MSFT", "GOOGL"])

**Returns:**
- `Dict[str, bool]`: Dictionary mapping each symbol to its validation status (True if valid, False if invalid)

**Raises:**
- `httpx.RequestError`: If network request fails
- `httpx.HTTPStatusError`: If API returns error status
- `ValidationError`: If symbols format is invalid

**Example:**
```python
import asyncio
from tvkit.api.utils import validate_symbols

async def main():
    # Validate multiple symbols
    symbols_to_check = ["AAPL", "MSFT", "INVALID_SYMBOL", "TSLA"]
    results = await validate_symbols(symbols_to_check)

    for symbol, is_valid in results.items():
        status = "✓ Valid" if is_valid else "✗ Invalid"
        print(f"{symbol}: {status}")

    # Filter only valid symbols
    valid_symbols = [symbol for symbol, valid in results.items() if valid]
    print(f"Valid symbols: {valid_symbols}")

# Run validation
asyncio.run(main())
```

### TradingView Indicator Functions

The module includes several TradingView-specific indicator functions that return structured data using Pydantic models:

#### get_sma_data

```python
def get_sma_data(period: int = 20) -> SMAIndicator
```

Returns Simple Moving Average indicator configuration.

**Parameters:**
- `period` (int, optional): SMA period in bars. Defaults to 20.

**Returns:**
- `SMAIndicator`: Pydantic model containing SMA configuration

#### get_ema_data

```python
def get_ema_data(period: int = 20) -> EMAIndicator
```

Returns Exponential Moving Average indicator configuration.

**Parameters:**
- `period` (int, optional): EMA period in bars. Defaults to 20.

**Returns:**
- `EMAIndicator`: Pydantic model containing EMA configuration

#### get_rsi_data

```python
def get_rsi_data(period: int = 14) -> RSIIndicator
```

Returns Relative Strength Index indicator configuration.

**Parameters:**
- `period` (int, optional): RSI period in bars. Defaults to 14.

**Returns:**
- `RSIIndicator`: Pydantic model containing RSI configuration

#### get_volume_data

```python
def get_volume_data() -> VolumeIndicator
```

Returns Volume indicator configuration.

**Returns:**
- `VolumeIndicator`: Pydantic model containing volume configuration

**Example:**
```python
from tvkit.api.utils import get_sma_data, get_ema_data, get_rsi_data, get_volume_data

# Get indicator configurations
sma_20 = get_sma_data(period=20)
sma_50 = get_sma_data(period=50)
ema_12 = get_ema_data(period=12)
rsi_14 = get_rsi_data(period=14)
volume = get_volume_data()

# Use with chart API
from tvkit.api.chart import OHLCV

async def get_data_with_indicators():
    client = OHLCV()

    # Get OHLCV data with technical indicators
    data = await client.get_ohlcv(
        symbol="NASDAQ:AAPL",
        interval="1D",
        indicators=[sma_20, sma_50, ema_12, rsi_14, volume]
    )

    return data
```

## Data Models

### Indicator Models

The module defines several Pydantic models for TradingView indicators:

```python
class SMAIndicator(BaseModel):
    """Simple Moving Average indicator model."""
    name: str = "SMA"
    period: int = Field(ge=1, le=1000, description="Period for SMA calculation")

class EMAIndicator(BaseModel):
    """Exponential Moving Average indicator model."""
    name: str = "EMA"
    period: int = Field(ge=1, le=1000, description="Period for EMA calculation")

class RSIIndicator(BaseModel):
    """Relative Strength Index indicator model."""
    name: str = "RSI"
    period: int = Field(ge=1, le=100, description="Period for RSI calculation")

class VolumeIndicator(BaseModel):
    """Volume indicator model."""
    name: str = "VOLUME"
```

## Usage Examples

### Basic Utility Usage

```python
import asyncio
from tvkit.api.utils import convert_timestamp_to_iso, validate_symbols

async def basic_utilities_example():
    # Timestamp conversion
    timestamps = [1640995200, 1641081600, 1641168000]
    iso_times = [convert_timestamp_to_iso(ts) for ts in timestamps]
    print("Converted timestamps:", iso_times)

    # Symbol validation
    symbols = ["AAPL", "MSFT", "GOOGL", "INVALID"]
    validation_results = await validate_symbols(symbols)

    valid_symbols = [s for s, valid in validation_results.items() if valid]
    invalid_symbols = [s for s, valid in validation_results.items() if not valid]

    print(f"Valid symbols: {valid_symbols}")
    print(f"Invalid symbols: {invalid_symbols}")

asyncio.run(basic_utilities_example())
```

### Integration with Chart API

```python
import asyncio
from tvkit.api.chart import OHLCV
from tvkit.api.utils import validate_symbols, get_sma_data, get_rsi_data

async def chart_integration_example():
    # Validate symbols before requesting data
    symbols_to_analyze = ["NASDAQ:AAPL", "NYSE:TSLA", "NASDAQ:MSFT"]
    validation_results = await validate_symbols(symbols_to_analyze)

    valid_symbols = [s for s, valid in validation_results.items() if valid]

    if not valid_symbols:
        print("No valid symbols found")
        return

    # Get technical indicators
    sma_20 = get_sma_data(period=20)
    rsi_14 = get_rsi_data(period=14)

    # Initialize OHLCV client
    client = OHLCV()

    # Fetch data for each valid symbol
    for symbol in valid_symbols:
        try:
            data = await client.get_ohlcv(
                symbol=symbol,
                interval="1H",
                indicators=[sma_20, rsi_14]
            )
            print(f"Successfully fetched data for {symbol}")

        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")

    await client.close()

asyncio.run(chart_integration_example())
```

### Batch Processing with Error Handling

```python
import asyncio
from typing import List, Dict, Any
from tvkit.api.utils import validate_symbols, convert_timestamp_to_iso
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def batch_processing_example():
    """Example of batch processing with comprehensive error handling."""

    # Large batch of symbols to validate
    symbols_batch = [
        "NASDAQ:AAPL", "NYSE:TSLA", "NASDAQ:MSFT", "NYSE:GOOGL",
        "NASDAQ:AMZN", "NYSE:META", "NASDAQ:NFLX", "NYSE:NVDA",
        "INVALID_SYMBOL_1", "INVALID_SYMBOL_2"
    ]

    try:
        # Validate symbols in batch
        logger.info(f"Validating {len(symbols_batch)} symbols...")
        validation_results = await validate_symbols(symbols_batch)

        # Process results
        valid_count = sum(validation_results.values())
        invalid_count = len(symbols_batch) - valid_count

        logger.info(f"Validation complete: {valid_count} valid, {invalid_count} invalid")

        # Generate timestamps for analysis periods
        import time
        current_time = int(time.time())
        timestamps = [
            current_time - (86400 * days)  # Go back N days
            for days in [1, 7, 30, 90]
        ]

        # Convert timestamps
        iso_times = []
        for ts in timestamps:
            try:
                iso_time = convert_timestamp_to_iso(ts)
                iso_times.append(iso_time)
            except (ValueError, OSError) as e:
                logger.error(f"Failed to convert timestamp {ts}: {e}")

        logger.info(f"Analysis periods: {iso_times}")

        return {
            'validation_results': validation_results,
            'analysis_periods': iso_times,
            'summary': {
                'total_symbols': len(symbols_batch),
                'valid_symbols': valid_count,
                'invalid_symbols': invalid_count
            }
        }

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise

# Run batch processing
result = asyncio.run(batch_processing_example())
print("Batch processing result:", result)
```

## Error Handling

### Common Exceptions

The utility functions handle several types of errors:

```python
import asyncio
from tvkit.api.utils import validate_symbols, convert_timestamp_to_iso
import logging

async def error_handling_example():
    """Demonstrate comprehensive error handling patterns."""

    # Handle timestamp conversion errors
    invalid_timestamps = [-1, 253402300800, "invalid"]  # Negative, far future, string

    for ts in invalid_timestamps:
        try:
            if isinstance(ts, (int, float)):
                iso_time = convert_timestamp_to_iso(int(ts))
                print(f"Converted {ts} to {iso_time}")
            else:
                print(f"Skipping invalid timestamp type: {type(ts)}")
        except ValueError as e:
            print(f"ValueError for timestamp {ts}: {e}")
        except OSError as e:
            print(f"OSError for timestamp {ts}: {e}")

    # Handle symbol validation errors
    try:
        # Test with various invalid inputs
        invalid_symbols = ["", None, 123, "SYMBOL_WITH_VERY_LONG_NAME"]

        # Filter out non-string values
        string_symbols = [s for s in invalid_symbols if isinstance(s, str) and s]

        if string_symbols:
            results = await validate_symbols(string_symbols)
            print(f"Validation results: {results}")
        else:
            print("No valid string symbols to validate")

    except Exception as e:
        print(f"Symbol validation error: {e}")

asyncio.run(error_handling_example())
```

### Retry Logic Pattern

```python
import asyncio
from typing import List, Dict
from tvkit.api.utils import validate_symbols
import logging

async def validate_symbols_with_retry(
    symbols: List[str],
    max_retries: int = 3,
    delay: float = 1.0
) -> Dict[str, bool]:
    """Validate symbols with retry logic for network resilience."""

    for attempt in range(max_retries):
        try:
            return await validate_symbols(symbols)

        except Exception as e:
            if attempt == max_retries - 1:
                logging.error(f"Symbol validation failed after {max_retries} attempts: {e}")
                raise

            logging.warning(f"Validation attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)
            delay *= 2  # Exponential backoff

# Usage
async def main():
    symbols = ["AAPL", "MSFT", "GOOGL"]
    try:
        results = await validate_symbols_with_retry(symbols)
        print(f"Validation successful: {results}")
    except Exception as e:
        print(f"All validation attempts failed: {e}")

asyncio.run(main())
```

## Performance Considerations

### Efficient Symbol Validation

- The `validate_symbols` function processes symbols in batches for optimal performance
- Use connection pooling by reusing the same HTTP client session
- Consider caching validation results for frequently used symbols

### Timestamp Processing

- `convert_timestamp_to_iso` is optimized for bulk operations
- Consider processing timestamps in batches when dealing with large datasets

### Memory Usage

- All utility functions are stateless and memory-efficient
- Pydantic models use slots for reduced memory footprint
- Consider using generators for large-scale data processing

## Integration Examples

### With Scanner API

```python
import asyncio
from tvkit.api.scanner import ScannerService, Market
from tvkit.api.utils import validate_symbols, convert_timestamp_to_iso

async def scanner_integration_example():
    """Integrate utils with scanner API for enhanced functionality."""

    # Get top performers from US market
    scanner = ScannerService()

    try:
        results = await scanner.scan_market(
            market=Market.UNITED_STATES,
            columns=['name', 'close', 'change', 'volume'],
            sort_by='change',
            sort_order='desc',
            range_size=10
        )

        # Extract symbols for validation
        symbols = [item.name for item in results.data]
        print(f"Top performers: {symbols}")

        # Validate symbols
        validation_results = await validate_symbols(symbols)
        valid_symbols = [s for s, valid in validation_results.items() if valid]

        print(f"Validated symbols: {valid_symbols}")

        # Add timestamp information
        import time
        scan_time = convert_timestamp_to_iso(int(time.time()))
        print(f"Scan completed at: {scan_time}")

    except Exception as e:
        print(f"Scanner integration error: {e}")

    finally:
        await scanner.close()

asyncio.run(scanner_integration_example())
```

### Custom Utility Composition

```python
from typing import List, Dict, Optional
from tvkit.api.utils import validate_symbols, convert_timestamp_to_iso, get_sma_data
import asyncio
import time

class TradingAnalysisUtils:
    """Custom utility class combining tvkit utils for trading analysis."""

    @staticmethod
    async def prepare_analysis_session(
        symbols: List[str],
        analysis_periods: List[int]  # Days back from now
    ) -> Dict[str, any]:
        """Prepare a complete analysis session with validated symbols and timestamps."""

        # Validate symbols
        validation_results = await validate_symbols(symbols)
        valid_symbols = [s for s, valid in validation_results.items() if valid]

        # Generate timestamps
        current_time = int(time.time())
        timestamps = {}

        for days_back in analysis_periods:
            timestamp = current_time - (86400 * days_back)
            iso_time = convert_timestamp_to_iso(timestamp)
            timestamps[f"{days_back}d_ago"] = {
                'unix': timestamp,
                'iso': iso_time
            }

        # Prepare technical indicators
        indicators = {
            'sma_20': get_sma_data(20),
            'sma_50': get_sma_data(50),
        }

        return {
            'symbols': {
                'valid': valid_symbols,
                'invalid': [s for s, valid in validation_results.items() if not valid],
                'validation_results': validation_results
            },
            'timestamps': timestamps,
            'indicators': indicators,
            'session_info': {
                'created_at': convert_timestamp_to_iso(current_time),
                'total_symbols': len(symbols),
                'valid_symbols_count': len(valid_symbols)
            }
        }

# Usage example
async def main():
    utils = TradingAnalysisUtils()

    session = await utils.prepare_analysis_session(
        symbols=['AAPL', 'MSFT', 'GOOGL', 'INVALID_SYM'],
        analysis_periods=[1, 7, 30]
    )

    print("Analysis session prepared:")
    print(f"Valid symbols: {session['symbols']['valid']}")
    print(f"Analysis periods: {list(session['timestamps'].keys())}")
    print(f"Session created: {session['session_info']['created_at']}")

asyncio.run(main())
```

## API Reference Summary

### Functions

| Function | Parameters | Returns | Description |
|----------|------------|---------|-------------|
| `convert_timestamp_to_iso` | `timestamp: int` | `str` | Converts Unix timestamp to ISO 8601 format |
| `validate_symbols` | `symbols: List[str]` | `Dict[str, bool]` | Validates trading symbols against TradingView API |
| `get_sma_data` | `period: int = 20` | `SMAIndicator` | Returns SMA indicator configuration |
| `get_ema_data` | `period: int = 20` | `EMAIndicator` | Returns EMA indicator configuration |
| `get_rsi_data` | `period: int = 14` | `RSIIndicator` | Returns RSI indicator configuration |
| `get_volume_data` | None | `VolumeIndicator` | Returns volume indicator configuration |

### Models

| Model | Fields | Description |
|-------|--------|-------------|
| `SMAIndicator` | `name: str`, `period: int` | Simple Moving Average indicator |
| `EMAIndicator` | `name: str`, `period: int` | Exponential Moving Average indicator |
| `RSIIndicator` | `name: str`, `period: int` | Relative Strength Index indicator |
| `VolumeIndicator` | `name: str` | Volume indicator |

### Exceptions

- `ValueError`: Invalid input parameters
- `OSError`: System-level errors (timestamp conversion)
- `httpx.RequestError`: Network request failures
- `httpx.HTTPStatusError`: API error responses
- `ValidationError`: Pydantic model validation errors

---

*This documentation is part of the tvkit library. For more information, see the main project documentation and examples.*