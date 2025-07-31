# OHLCV Client Methods

This document provides comprehensive usage documentation for all public methods in the OHLCV client module.

**Module**: `tvkit.api.chart.ohlcv.py`

The OHLCV client provides async methods for streaming and retrieving OHLCV (Open, High, Low, Close, Volume) and quote data from TradingView's WebSocket API.

## Table of Contents

- [Constructor](#constructor)
- [Real-time Streaming Methods](#real-time-streaming-methods)
- [Historical Data Methods](#historical-data-methods)
- [Quote Data Methods](#quote-data-methods)
- [Raw Data Methods](#raw-data-methods)
- [Multi-Symbol Methods](#multi-symbol-methods)
- [Error Handling](#error-handling)

---

## Constructor

### `__init__()`

```python
def __init__(self) -> None
```

Initializes the OHLCV class, setting up WebSocket connection parameters and request headers for TradingView data streaming.

#### Parameters
- None

#### Returns
- None

#### Example
```python
from tvkit.api.chart.ohlcv import OHLCV

client = OHLCV()
```

---

## Real-time Streaming Methods

### `get_ohlcv()`

```python
async def get_ohlcv(
    self, 
    exchange_symbol: str, 
    interval: str = "1", 
    bars_count: int = 10
) -> AsyncGenerator[OHLCVBar, None]
```

Returns an async generator that yields OHLC data for a specified symbol in real-time. This is the primary method for streaming structured OHLCV data from TradingView.

#### Parameters
- `exchange_symbol` (str): The symbol in the format 'EXCHANGE:SYMBOL' (e.g., 'BINANCE:BTCUSDT')
- `interval` (str, optional): The interval for the chart (default is "1" for 1 minute)
- `bars_count` (int, optional): The number of bars to fetch (default is 10)

#### Returns
- `AsyncGenerator[OHLCVBar, None]`: An async generator yielding structured OHLCV data as OHLCVBar objects

#### Raises
- `ValueError`: If the symbol format is invalid
- `WebSocketException`: If connection or streaming fails

#### Example
```python
async with OHLCV() as client:
    async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="5"):
        print(f"Close: ${bar.close}, Volume: {bar.volume}")
        print(f"Timestamp: {bar.timestamp}")
```

#### Example Output
```
Close: $45672.50, Volume: 1250.75
Timestamp: 1704067200
Close: $45680.25, Volume: 985.32
Timestamp: 1704067260
Close: $45695.10, Volume: 1832.44
Timestamp: 1704067320
```

---

## Historical Data Methods

### `get_historical_ohlcv()`

```python
async def get_historical_ohlcv(
    self, 
    exchange_symbol: str, 
    interval: str = "1", 
    bars_count: int = 10
) -> list[OHLCVBar]
```

Returns a list of historical OHLCV data for a specified symbol. This method fetches historical OHLCV data from TradingView and returns it as a list of OHLCVBar objects.

#### Parameters
- `exchange_symbol` (str): The symbol in the format 'EXCHANGE:SYMBOL' (e.g., 'BINANCE:BTCUSDT')
- `interval` (str, optional): The interval for the chart (default is "1" for 1 minute)
- `bars_count` (int, optional): The number of bars to fetch (default is 10)

#### Returns
- `list[OHLCVBar]`: A list of OHLCVBar objects containing historical OHLCV data

#### Raises
- `ValueError`: If the symbol format is invalid
- `WebSocketException`: If connection or streaming fails
- `RuntimeError`: If no historical data is received

#### Example
```python
async with OHLCV() as client:
    bars = await client.get_historical_ohlcv("BINANCE:BTCUSDT", "1D", 5)
    for bar in bars:
        print(f"Date: {bar.timestamp}, Close: ${bar.close}")
```

#### Example Output
```python
[
    OHLCVBar(timestamp=1704067200, open=42150.0, high=42350.0, low=41980.0, close=42100.0, volume=1250.75),
    OHLCVBar(timestamp=1704153600, open=42100.0, high=42580.0, low=42050.0, close=42450.0, volume=1832.44),
    OHLCVBar(timestamp=1704240000, open=42450.0, high=42750.0, low=42200.0, close=42680.0, volume=2145.33),
    OHLCVBar(timestamp=1704326400, open=42680.0, high=43120.0, low=42580.0, close=43050.0, volume=1955.28),
    OHLCVBar(timestamp=1704412800, open=43050.0, high=43280.0, low=42880.0, close=43150.0, volume=1678.92)
]
```

---

## Quote Data Methods

### `get_quote_data()`

```python
async def get_quote_data(
    self, 
    exchange_symbol: str, 
    interval: str = "1", 
    bars_count: int = 10
) -> AsyncGenerator[QuoteSymbolData, None]
```

Returns an async generator that yields quote data for a specified symbol in real-time. This method is useful for symbols that provide quote data but may not have OHLCV chart data available.

#### Parameters
- `exchange_symbol` (str): The symbol in the format 'EXCHANGE:SYMBOL' (e.g., 'NASDAQ:AAPL')
- `interval` (str, optional): The interval for the chart (default is "1" for 1 minute)
- `bars_count` (int, optional): The number of bars to fetch (default is 10)

#### Returns
- `AsyncGenerator[QuoteSymbolData, None]`: An async generator yielding quote data as QuoteSymbolData objects

#### Raises
- `ValueError`: If the symbol format is invalid
- `WebSocketException`: If connection or streaming fails

#### Example
```python
async with OHLCV() as client:
    async for quote in client.get_quote_data("NASDAQ:AAPL", interval="5"):
        print(f"Price: ${quote.current_price}")
        print(f"Symbol: {quote.symbol_info}")
```

#### Example Output
```
Price: $185.42
Symbol: {'name': 'AAPL', 'exchange': 'NASDAQ', 'currency': 'USD'}
Price: $185.38
Symbol: {'name': 'AAPL', 'exchange': 'NASDAQ', 'currency': 'USD'}
Price: $185.45
Symbol: {'name': 'AAPL', 'exchange': 'NASDAQ', 'currency': 'USD'}
```

---

## Raw Data Methods

### `get_ohlcv_raw()`

```python
async def get_ohlcv_raw(
    self, 
    exchange_symbol: str, 
    interval: str = "1", 
    bars_count: int = 10
) -> AsyncGenerator[dict[str, Any], None]
```

Returns an async generator that yields raw OHLC data for a specified symbol in real-time. This method provides the raw JSON data from TradingView for debugging purposes.

#### Parameters
- `exchange_symbol` (str): The symbol in the format 'EXCHANGE:SYMBOL'
- `interval` (str, optional): The interval for the chart (default is "1" for 1 minute)
- `bars_count` (int, optional): The number of bars to fetch (default is 10)

#### Returns
- `AsyncGenerator[dict[str, Any], None]`: An async generator yielding raw OHLC data as JSON dictionary objects

#### Raises
- `ValueError`: If the symbol format is invalid
- `WebSocketException`: If connection or streaming fails

#### Example
```python
async with OHLCV() as client:
    count = 0
    async for raw_data in client.get_ohlcv_raw("BINANCE:BTCUSDT", interval="5"):
        print(f"Raw message: {raw_data}")
        count += 1
        if count >= 3:  # Limit output for example
            break
```

#### Example Output
```python
{
    "message_type": "du",
    "session": "cs_abc123",
    "data": {
        "lbs": {
            "bar_count": 1,
            "bars": [[1704067200, 42150.0, 42350.0, 41980.0, 42100.0, 1250.75]]
        }
    }
}
{
    "message_type": "qsd",
    "symbol": "BINANCE:BTCUSDT",
    "data": {
        "current_price": 42100.0,
        "volume": 125000.0
    }
}
{
    "message_type": "quote_completed",
    "symbol": "BINANCE:BTCUSDT"
}
```

---

## Multi-Symbol Methods

### `get_latest_trade_info()`

```python
async def get_latest_trade_info(
    self, 
    exchange_symbol: List[str]
) -> AsyncGenerator[dict[str, Any], None]
```

Returns summary information about multiple symbols including last changes, change percentage, and last trade time. This method allows you to monitor multiple symbols simultaneously.

#### Parameters
- `exchange_symbol` (List[str]): A list of symbols in the format 'EXCHANGE:SYMBOL'

#### Returns
- `AsyncGenerator[dict[str, Any], None]`: An async generator yielding summary information as JSON dictionary objects

#### Raises
- `ValueError`: If any symbol format is invalid
- `WebSocketException`: If connection or streaming fails

#### Example
```python
symbols = ["BINANCE:BTCUSDT", "NASDAQ:AAPL", "FOREX:EURUSD"]
async with OHLCV() as client:
    count = 0
    async for trade_info in client.get_latest_trade_info(symbols):
        print(f"Trade info: {trade_info}")
        count += 1
        if count >= 5:  # Limit output for example
            break
```

#### Example Output
```python
{
    "message_type": "qsd",
    "symbol": "BINANCE:BTCUSDT",
    "data": {
        "current_price": 42100.0,
        "change": 150.0,
        "change_percent": 0.357,
        "volume": 125000.0,
        "last_update": 1704067200
    }
}
{
    "message_type": "qsd",
    "symbol": "NASDAQ:AAPL",
    "data": {
        "current_price": 185.42,
        "change": -2.15,
        "change_percent": -1.147,
        "volume": 45000000.0,
        "last_update": 1704067205
    }
}
{
    "message_type": "qsd",
    "symbol": "FOREX:EURUSD",
    "data": {
        "current_price": 1.0895,
        "change": 0.0023,
        "change_percent": 0.211,
        "volume": 0.0,
        "last_update": 1704067210
    }
}
```

---

## Error Handling

### Common Exceptions

- **WebSocketException**: Connection or streaming failures
- **ValueError**: Invalid symbol format or parameters
- **RuntimeError**: Service initialization or data retrieval failures

### Async Context Management

The OHLCV client supports async context managers for automatic connection management:

```python
async with OHLCV() as client:
    # WebSocket connection automatically managed
    data = await client.get_historical_ohlcv("BINANCE:BTCUSDT")
    # Connection automatically closed when exiting context
```

### Best Practices

1. **Always use async context managers** to ensure proper connection cleanup
2. **Handle specific exceptions** for robust error handling
3. **Validate symbols** before making requests
4. **Use appropriate intervals** based on your data needs
5. **Limit bars_count** for initial testing to avoid overwhelming data
6. **Implement timeout logic** for long-running streams

### Example with Error Handling

```python
from tvkit.api.chart.ohlcv import OHLCV
import asyncio

async def fetch_with_error_handling():
    try:
        async with OHLCV() as client:
            bars = await client.get_historical_ohlcv(
                "BINANCE:BTCUSDT", 
                interval="1D", 
                bars_count=10
            )
            print(f"Successfully fetched {len(bars)} bars")
            return bars
    except ValueError as e:
        print(f"Invalid parameters: {e}")
    except RuntimeError as e:
        print(f"Service error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    return []

# Run the function
bars = await fetch_with_error_handling()
```