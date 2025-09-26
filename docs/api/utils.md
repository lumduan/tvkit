# tvkit.api.utils

## Overview

The `tvkit.api.utils` package provides essential utility functions for validating exchange symbols and fetching TradingView indicators and their metadata. This package is organized into focused modules for better maintainability and type safety, while maintaining backward compatibility through its main package interface.

## Package Structure

The utils package is organized into the following modules:

```
tvkit/api/utils/
├── __init__.py              # Package exports and backward compatibility
├── models.py                # Pydantic data models
├── timestamp.py             # Timestamp conversion utilities
├── symbol_validator.py      # Symbol validation service
└── indicator_service.py     # TradingView indicator management
```

## Architecture

The package is designed with a modular architecture, separating concerns into focused modules:

- **`models.py`**: Contains all Pydantic data models for type safety and validation
- **`timestamp.py`**: Timestamp conversion utilities for TradingView data
- **`symbol_validator.py`**: Symbol validation against TradingView's API
- **`indicator_service.py`**: TradingView indicator search, selection, and metadata management

### Key Components

- **Timestamp Utilities**: Convert between Unix timestamps and ISO 8601 format
- **Symbol Validation**: Async validation of trading symbols against TradingView API
- **TradingView Indicator Search**: Search and fetch TradingView indicators
- **Interactive Indicator Selection**: User-friendly indicator selection interface
- **Metadata Processing**: Pine script metadata preparation for indicator creation
- **Type-Safe Models**: Comprehensive Pydantic models for all data structures

## Functions

### timestamp.convert_timestamp_to_iso

```python
def convert_timestamp_to_iso(timestamp: float) -> str
```

Convert a Unix timestamp to ISO 8601 format string.

This function converts TradingView timestamps (Unix epoch seconds) to human-readable ISO 8601 format with UTC timezone.

**Parameters:**
- `timestamp` (float): Unix timestamp as a float (seconds since epoch)

**Returns:**
- `str`: ISO 8601 formatted datetime string with UTC timezone

**Example:**
```python
from tvkit.api.utils import convert_timestamp_to_iso

# Convert Unix timestamp to ISO format
timestamp = 1753436820.0
iso_time = convert_timestamp_to_iso(timestamp)
print(iso_time)  # '2025-07-28T12:13:40+00:00'

# Handle current time
import time
current_timestamp = time.time()
current_iso = convert_timestamp_to_iso(current_timestamp)
print(f"Current time: {current_iso}")
```

### symbol_validator.validate_symbols

```python
async def validate_symbols(exchange_symbol: Union[str, List[str]]) -> bool
```

Validate one or more exchange symbols asynchronously.

This function validates trading symbols by making requests to TradingView's symbol URL endpoint. Symbols can be in various formats including "EXCHANGE:SYMBOL" format or other TradingView-compatible formats like "USI-PCC". The validation considers both 200 and 301 HTTP status codes as successful validation.

**Parameters:**
- `exchange_symbol` (Union[str, List[str]]): A single symbol or a list of symbols to validate. Supports formats like "BINANCE:BTCUSDT", "USI-PCC", "NASDAQ:AAPL", etc.

**Returns:**
- `bool`: True if all provided symbols are valid

**Raises:**
- `ValueError`: If exchange_symbol is empty or if the symbol fails validation (returns 404 - "Invalid exchange or symbol or index")
- `httpx.HTTPError`: If there's an HTTP-related error during validation

**Example:**
```python
import asyncio
from tvkit.api.utils import validate_symbols

async def main():
    # Validate single symbol with standard format
    is_valid = await validate_symbols("BINANCE:BTCUSDT")
    print(f"Bitcoin symbol valid: {is_valid}")

    # Validate symbol with alternative format
    is_valid = await validate_symbols("USI-PCC")
    print(f"Alternative format valid: {is_valid}")

    # Validate multiple symbols with mixed formats
    symbols = ["BINANCE:BTCUSDT", "NASDAQ:AAPL", "USI-PCC"]
    is_valid = await validate_symbols(symbols)
    print(f"Multiple symbols valid: {is_valid}")

    # Handle validation errors
    try:
        await validate_symbols("INVALID:SYMBOL123")
    except ValueError as e:
        print(f"Validation error: {e}")

asyncio.run(main())
```

### indicator_service.fetch_tradingview_indicators

```python
async def fetch_tradingview_indicators(query: str) -> List[IndicatorData]
```

Fetch TradingView indicators based on a search query asynchronously.

This function sends a GET request to the TradingView public endpoint for indicator suggestions and filters the results by checking if the search query appears in either the script name or the author's username.

**Parameters:**
- `query` (str): The search term used to filter indicators by script name or author

**Returns:**
- `List[IndicatorData]`: A list of IndicatorData objects containing details of matching indicators

**Raises:**
- `httpx.HTTPError`: If there's an HTTP-related error during the request

**Example:**
```python
import asyncio
from tvkit.api.utils import fetch_tradingview_indicators

async def main():
    # Search for RSI indicators
    indicators = await fetch_tradingview_indicators("RSI")

    for indicator in indicators:
        print(f"Indicator: {indicator.script_name}")
        print(f"Author: {indicator.author}")
        print(f"Agree Count: {indicator.agree_count}")
        print(f"Recommended: {indicator.is_recommended}")
        print("---")

asyncio.run(main())
```

### indicator_service.display_and_select_indicator

```python
def display_and_select_indicator(indicators: List[IndicatorData]) -> Optional[Tuple[Optional[str], Optional[str]]]
```

Display a list of indicators and prompt the user to select one.

This function prints the available indicators with numbering, waits for the user to input the number corresponding to their preferred indicator, and returns the selected indicator's scriptId and version.

**Parameters:**
- `indicators` (List[IndicatorData]): A list of IndicatorData objects containing indicator details

**Returns:**
- `Optional[Tuple[Optional[str], Optional[str]]]`: A tuple (scriptId, version) of the selected indicator if the selection is valid; otherwise, None

**Example:**
```python
import asyncio
from tvkit.api.utils import fetch_tradingview_indicators, display_and_select_indicator

async def main():
    # Fetch indicators
    indicators = await fetch_tradingview_indicators("RSI")

    # Display and let user select
    result = display_and_select_indicator(indicators)

    if result:
        script_id, version = result
        print(f"Selected script ID: {script_id}, version: {version}")
    else:
        print("No indicator selected")

asyncio.run(main())
```

### indicator_service.fetch_indicator_metadata

```python
async def fetch_indicator_metadata(script_id: str, script_version: str, chart_session: str) -> Dict[str, Any]
```

Fetch metadata for a TradingView indicator based on its script ID and version asynchronously.

This function constructs a URL using the provided script ID and version, sends a GET request to fetch the indicator metadata, and then prepares the metadata for further processing using the chart session.

**Parameters:**
- `script_id` (str): The unique identifier for the indicator script
- `script_version` (str): The version of the indicator script
- `chart_session` (str): The chart session identifier used in further processing

**Returns:**
- `Dict[str, Any]`: A dictionary containing the prepared indicator metadata if successful; an empty dictionary if an error occurs

**Raises:**
- `httpx.HTTPError`: If there's an HTTP-related error during the request

**Example:**
```python
import asyncio
from tvkit.api.utils import fetch_indicator_metadata

async def main():
    # Fetch metadata for a specific indicator
    metadata = await fetch_indicator_metadata(
        script_id="PUB;123",
        script_version="1.0",
        chart_session="session123"
    )

    if metadata:
        print("Metadata fetched successfully")
        print(f"Method: {metadata.get('m')}")
        print(f"Parameters count: {len(metadata.get('p', []))}")
    else:
        print("Failed to fetch metadata")

asyncio.run(main())
```

### indicator_service.prepare_indicator_metadata

```python
def prepare_indicator_metadata(script_id: str, metainfo: Dict[str, Any], chart_session: str) -> Dict[str, Any]
```

Prepare indicator metadata into the required payload structure.

This function constructs a dictionary payload for creating a study (indicator) session. It extracts default input values and metadata from the provided metainfo and combines them with the provided script ID and chart session.

**Parameters:**
- `script_id` (str): The unique identifier for the indicator script
- `metainfo` (Dict[str, Any]): A dictionary containing metadata information for the indicator
- `chart_session` (str): The chart session identifier

**Returns:**
- `Dict[str, Any]`: A dictionary representing the payload required to create a study with the indicator

**Example:**
```python
from tvkit.api.utils import prepare_indicator_metadata

# Example metainfo structure
metainfo = {
    "inputs": [
        {"defval": "test", "id": "in_param1", "type": "string"}
    ],
    "pine": {"version": "5"}
}

payload = prepare_indicator_metadata("PUB;123", metainfo, "session123")
print(f"Method: {payload['m']}")  # "create_study"
print(f"Parameters: {len(payload['p'])}")  # Number of parameters
```

## Data Models

All data models are defined in `models.py` and use Pydantic for validation and type safety.

### models.IndicatorData

```python
class IndicatorData(BaseModel):
    """Data structure for TradingView indicator information."""

    script_name: str = Field(..., description="Name of the indicator script")
    image_url: str = Field(..., description="URL of the indicator image")
    author: str = Field(..., description="Author username")
    agree_count: int = Field(..., ge=0, description="Number of agree votes")
    is_recommended: bool = Field(..., description="Whether the indicator is recommended")
    script_id_part: str = Field(..., description="Script ID part for the indicator")
    version: Optional[str] = Field(None, description="Version of the indicator script")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
```

### models.PineFeatures

```python
class PineFeatures(BaseModel):
    """Pydantic model for Pine script features configuration."""

    v: str = Field(..., description="Pine features JSON string")
    f: bool = Field(True, description="Features flag")
    t: str = Field("text", description="Type identifier")
```

### models.ProfileConfig

```python
class ProfileConfig(BaseModel):
    """Pydantic model for profile configuration."""

    v: bool = Field(False, description="Profile value")
    f: bool = Field(True, description="Profile flag")
    t: str = Field("bool", description="Type identifier")
```

### models.InputValue

```python
class InputValue(BaseModel):
    """Pydantic model for input value configuration."""

    v: Any = Field(..., description="Input value")
    f: bool = Field(True, description="Input flag")
    t: str = Field(..., description="Input type")
```

### models.StudyPayload

```python
class StudyPayload(BaseModel):
    """Pydantic model for study creation payload."""

    m: str = Field("create_study", description="Method name")
    p: List[Any] = Field(..., description="Parameters list")
```

## Usage Examples

### Basic Symbol Validation

```python
import asyncio
from tvkit.api.utils import validate_symbols

async def basic_validation_example():
    """Basic symbol validation example."""

    # Validate single symbol with standard format
    try:
        is_valid = await validate_symbols("BINANCE:BTCUSDT")
        print(f"BINANCE:BTCUSDT is valid: {is_valid}")
    except ValueError as e:
        print(f"Validation error: {e}")

    # Validate symbol with alternative format
    try:
        is_valid = await validate_symbols("USI-PCC")
        print(f"USI-PCC is valid: {is_valid}")
    except ValueError as e:
        print(f"Validation error: {e}")

    # Validate multiple symbols with mixed formats
    symbols = ["NASDAQ:AAPL", "NYSE:TSLA", "USI-PCC"]
    try:
        is_valid = await validate_symbols(symbols)
        print(f"All symbols valid: {is_valid}")
    except ValueError as e:
        print(f"Validation error: {e}")

    # Test invalid symbol (will raise ValueError with "Invalid exchange or symbol or index")
    try:
        await validate_symbols("INVALID:SYMBOL123")
    except ValueError as e:
        print(f"Expected validation error: {e}")

asyncio.run(basic_validation_example())
```

### Complete Indicator Search and Selection Workflow

```python
import asyncio
from tvkit.api.utils import (
    fetch_tradingview_indicators,
    display_and_select_indicator,
    fetch_indicator_metadata
)

async def complete_indicator_workflow():
    """Complete workflow for finding and selecting TradingView indicators."""

    # Step 1: Search for indicators
    query = "RSI"
    print(f"Searching for '{query}' indicators...")

    indicators = await fetch_tradingview_indicators(query)

    if not indicators:
        print("No indicators found")
        return

    print(f"Found {len(indicators)} indicators")

    # Step 2: Display and select indicator
    selection = display_and_select_indicator(indicators)

    if not selection:
        print("No indicator selected")
        return

    script_id, version = selection
    print(f"Selected: {script_id}, version: {version}")

    # Step 3: Fetch metadata for the selected indicator
    chart_session = "chart_session_123"

    metadata = await fetch_indicator_metadata(
        script_id=script_id,
        script_version=version or "1",
        chart_session=chart_session
    )

    if metadata:
        print("Successfully fetched indicator metadata")
        print(f"Payload method: {metadata.get('m')}")
        print(f"Parameters count: {len(metadata.get('p', []))}")
    else:
        print("Failed to fetch indicator metadata")

# Run the complete workflow
asyncio.run(complete_indicator_workflow())
```

### Timestamp Processing with Error Handling

```python
from tvkit.api.utils import convert_timestamp_to_iso
import time

def timestamp_processing_example():
    """Example of timestamp processing with error handling."""

    # Process various timestamps
    timestamps = [
        time.time(),           # Current time
        1640995200.0,         # New Year 2022
        1753436820.0,         # Future timestamp
    ]

    for ts in timestamps:
        try:
            iso_time = convert_timestamp_to_iso(ts)
            print(f"Timestamp {ts} -> {iso_time}")
        except (ValueError, OSError) as e:
            print(f"Error converting {ts}: {e}")

    # Handle invalid timestamps
    invalid_timestamps = [-1, "invalid", None]

    for ts in invalid_timestamps:
        try:
            if isinstance(ts, (int, float)):
                iso_time = convert_timestamp_to_iso(ts)
                print(f"Converted {ts} -> {iso_time}")
            else:
                print(f"Skipping invalid type {type(ts)}: {ts}")
        except Exception as e:
            print(f"Error with {ts}: {e}")

timestamp_processing_example()
```

### Modular Import Examples

```python
# Import specific services
from tvkit.api.utils.timestamp import convert_timestamp_to_iso
from tvkit.api.utils.symbol_validator import validate_symbols
from tvkit.api.utils.indicator_service import fetch_tradingview_indicators
from tvkit.api.utils.models import IndicatorData, StudyPayload

# Or use the main package interface (recommended for backward compatibility)
from tvkit.api.utils import (
    convert_timestamp_to_iso,
    validate_symbols,
    fetch_tradingview_indicators,
    IndicatorData,
    StudyPayload
)
```

### Batch Indicator Processing

```python
import asyncio
from typing import List
from tvkit.api.utils import fetch_tradingview_indicators, IndicatorData

async def batch_indicator_processing():
    """Process multiple indicator searches in batch."""

    search_terms = ["RSI", "MACD", "Moving Average", "Bollinger", "Stochastic"]
    all_indicators: List[IndicatorData] = []

    print("Searching for indicators...")

    # Fetch indicators for all search terms
    for term in search_terms:
        try:
            indicators = await fetch_tradingview_indicators(term)
            all_indicators.extend(indicators)
            print(f"Found {len(indicators)} indicators for '{term}'")
        except Exception as e:
            print(f"Error searching for '{term}': {e}")

    # Remove duplicates based on script_id_part
    unique_indicators = {}
    for indicator in all_indicators:
        unique_indicators[indicator.script_id_part] = indicator

    print(f"\nTotal unique indicators found: {len(unique_indicators)}")

    # Display top rated indicators
    sorted_indicators = sorted(
        unique_indicators.values(),
        key=lambda x: x.agree_count,
        reverse=True
    )

    print("\nTop 10 most agreed indicators:")
    for i, indicator in enumerate(sorted_indicators[:10], 1):
        print(f"{i}. {indicator.script_name} by {indicator.author}")
        print(f"   Agrees: {indicator.agree_count}, Recommended: {indicator.is_recommended}")

asyncio.run(batch_indicator_processing())
```

## Error Handling

### Symbol Validation Errors

```python
import asyncio
from tvkit.api.utils import validate_symbols
import logging

logging.basicConfig(level=logging.INFO)

async def symbol_validation_error_handling():
    """Demonstrate comprehensive error handling for symbol validation."""

    # Test various invalid inputs and formats
    test_cases = [
        "",                           # Empty string
        [],                          # Empty list
        "INVALID-SYMBOL123",         # Invalid symbol
        "NONEXISTENT:FAKE",          # Non-existent symbol
        ["NASDAQ:AAPL", "INVALID123"], # Mixed valid/invalid
        "USI-PCC",                   # Alternative format (should be valid)
    ]

    for test_case in test_cases:
        try:
            print(f"Testing: {test_case}")
            result = await validate_symbols(test_case)
            print(f"✓ Valid: {result}")
        except ValueError as e:
            print(f"✗ ValueError: {e}")
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
        print()

asyncio.run(symbol_validation_error_handling())
```

### Network Error Handling

```python
import asyncio
import httpx
from tvkit.api.utils import fetch_tradingview_indicators

async def network_error_handling():
    """Handle network-related errors gracefully."""

    # Test with various network conditions
    test_queries = ["RSI", "MACD", "Invalid_Query_That_Might_Fail"]

    for query in test_queries:
        try:
            indicators = await fetch_tradingview_indicators(query)
            print(f"✓ Found {len(indicators)} indicators for '{query}'")

        except httpx.RequestError as e:
            print(f"✗ Network error for '{query}': {e}")

        except httpx.HTTPStatusError as e:
            print(f"✗ HTTP error for '{query}': {e.response.status_code}")

        except Exception as e:
            print(f"✗ Unexpected error for '{query}': {e}")

asyncio.run(network_error_handling())
```

### Retry Logic for Robust Operations

```python
import asyncio
from typing import List
from tvkit.api.utils import validate_symbols, fetch_tradingview_indicators, IndicatorData

async def retry_operation(operation, *args, max_retries=3, delay=1.0):
    """Generic retry wrapper for async operations."""

    for attempt in range(max_retries):
        try:
            return await operation(*args)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)
            delay *= 2  # Exponential backoff

async def robust_operations_example():
    """Example using retry logic for robust operations."""

    # Robust symbol validation
    try:
        result = await retry_operation(validate_symbols, ["NASDAQ:AAPL", "NYSE:TSLA"])
        print(f"Validation successful: {result}")
    except Exception as e:
        print(f"Validation failed after retries: {e}")

    # Robust indicator search
    try:
        indicators = await retry_operation(fetch_tradingview_indicators, "RSI")
        print(f"Found {len(indicators)} indicators")
    except Exception as e:
        print(f"Indicator search failed after retries: {e}")

asyncio.run(robust_operations_example())
```

## Performance Considerations

### Efficient Symbol Validation

- The `validate_symbols` function validates symbols with built-in retry logic (3 attempts)
- Use connection pooling by reusing HTTP clients for multiple validation calls
- Batch symbol validation when possible to reduce network overhead

### Indicator Search Optimization

- Cache frequently searched indicators to reduce API calls
- Use specific search terms to get more relevant results
- Consider implementing local filtering for better performance

### Memory Management

- All Pydantic models are frozen (immutable) for better memory efficiency
- Use async/await patterns to prevent blocking operations
- Process large indicator lists in batches to manage memory usage

## Integration Examples

### Integration with Chart API

```python
import asyncio
from tvkit.api.utils import validate_symbols
from tvkit.api.chart.ohlcv import OHLCV

async def chart_integration_example():
    """Integrate utils with chart API for validated streaming."""

    # Step 1: Validate symbols before streaming
    symbols_to_stream = ["BINANCE:BTCUSDT", "NASDAQ:AAPL", "FOREX:EURUSD"]

    try:
        is_valid = await validate_symbols(symbols_to_stream)
        print(f"All symbols valid: {is_valid}")
    except ValueError as e:
        print(f"Symbol validation failed: {e}")
        return

    # Step 2: Stream data for validated symbols
    async with OHLCV() as client:
        for symbol in symbols_to_stream:
            try:
                # Get recent historical data
                bars = await client.get_historical_ohlcv(symbol, "1H", 5)
                print(f"{symbol}: Latest price ${bars[-1].close}")
            except Exception as e:
                print(f"Error fetching data for {symbol}: {e}")

asyncio.run(chart_integration_example())
```

### Custom Indicator Management System

```python
import asyncio
import json
from typing import Dict, List, Optional
from tvkit.api.utils import (
    fetch_tradingview_indicators,
    fetch_indicator_metadata,
    IndicatorData
)

class IndicatorManager:
    """Custom indicator management system using tvkit utilities."""

    def __init__(self):
        self.indicators_cache: Dict[str, List[IndicatorData]] = {}
        self.metadata_cache: Dict[str, Dict] = {}

    async def search_and_cache_indicators(self, query: str) -> List[IndicatorData]:
        """Search for indicators and cache results."""

        if query in self.indicators_cache:
            print(f"Using cached results for '{query}'")
            return self.indicators_cache[query]

        indicators = await fetch_tradingview_indicators(query)
        self.indicators_cache[query] = indicators
        print(f"Cached {len(indicators)} indicators for '{query}'")

        return indicators

    async def get_indicator_metadata(self, script_id: str, version: str, session: str) -> Dict:
        """Get indicator metadata with caching."""

        cache_key = f"{script_id}:{version}"

        if cache_key in self.metadata_cache:
            print(f"Using cached metadata for {cache_key}")
            return self.metadata_cache[cache_key]

        metadata = await fetch_indicator_metadata(script_id, version, session)
        if metadata:
            self.metadata_cache[cache_key] = metadata
            print(f"Cached metadata for {cache_key}")

        return metadata

    def save_cache_to_file(self, filename: str):
        """Save cache to JSON file."""

        # Convert IndicatorData objects to dictionaries
        cache_data = {
            "indicators": {
                query: [ind.to_dict() for ind in indicators]
                for query, indicators in self.indicators_cache.items()
            },
            "metadata": self.metadata_cache
        }

        with open(filename, 'w') as f:
            json.dump(cache_data, f, indent=2)

        print(f"Cache saved to {filename}")

# Usage example
async def main():
    manager = IndicatorManager()

    # Search for different types of indicators
    queries = ["RSI", "MACD", "Volume"]

    for query in queries:
        indicators = await manager.search_and_cache_indicators(query)
        print(f"Found {len(indicators)} indicators for {query}")

    # Save cache for future use
    manager.save_cache_to_file("indicators_cache.json")

asyncio.run(main())
```

## Module Reference

### Package Import Patterns

```python
# Backward-compatible imports (recommended)
from tvkit.api.utils import convert_timestamp_to_iso, validate_symbols

# Direct module imports (for specific use cases)
from tvkit.api.utils.timestamp import convert_timestamp_to_iso
from tvkit.api.utils.symbol_validator import validate_symbols
from tvkit.api.utils.indicator_service import fetch_tradingview_indicators
from tvkit.api.utils.models import IndicatorData
```

### API Reference Summary

| Module | Functions | Models | Description |
|--------|-----------|--------|-------------|
| `timestamp.py` | `convert_timestamp_to_iso` | - | Timestamp conversion utilities |
| `symbol_validator.py` | `validate_symbols` | - | Symbol validation against TradingView API |
| `indicator_service.py` | `fetch_tradingview_indicators`, `display_and_select_indicator`, `fetch_indicator_metadata`, `prepare_indicator_metadata` | - | TradingView indicator management |
| `models.py` | - | `IndicatorData`, `PineFeatures`, `ProfileConfig`, `InputValue`, `StudyPayload` | Pydantic data models |

### Functions

| Function | Parameters | Returns | Description |
|----------|------------|---------|-------------|
| `convert_timestamp_to_iso` | `timestamp: float` | `str` | Converts Unix timestamp to ISO 8601 format |
| `validate_symbols` | `exchange_symbol: Union[str, List[str]]` | `bool` | Validates trading symbols against TradingView API |
| `fetch_tradingview_indicators` | `query: str` | `List[IndicatorData]` | Fetches TradingView indicators based on search query |
| `display_and_select_indicator` | `indicators: List[IndicatorData]` | `Optional[Tuple[str, str]]` | Interactive indicator selection interface |
| `fetch_indicator_metadata` | `script_id: str, script_version: str, chart_session: str` | `Dict[str, Any]` | Fetches metadata for TradingView indicator |
| `prepare_indicator_metadata` | `script_id: str, metainfo: Dict, chart_session: str` | `Dict[str, Any]` | Prepares indicator metadata payload |

### Models

| Model | Key Fields | Description |
|-------|------------|-------------|
| `IndicatorData` | `script_name`, `author`, `agree_count`, `is_recommended` | TradingView indicator information |
| `PineFeatures` | `v`, `f`, `t` | Pine script features configuration |
| `ProfileConfig` | `v`, `f`, `t` | Profile configuration for indicators |
| `InputValue` | `v`, `f`, `t` | Input value configuration |
| `StudyPayload` | `m`, `p` | Study creation payload structure |

### Exceptions

- `ValueError`: Invalid input parameters or symbol formats
- `httpx.RequestError`: Network request failures
- `httpx.HTTPStatusError`: API error responses
- `httpx.HTTPError`: General HTTP-related errors

---

*This documentation reflects the modular structure of the tvkit.api.utils package. All functions remain accessible through the main package interface for backward compatibility, while the new modular structure provides better organization and maintainability.*