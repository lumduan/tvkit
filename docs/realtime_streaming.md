# Real-time Data Streaming Module

A comprehensive async-first implementation for streaming real-time market data from TradingView WebSocket connections.

## Features

- 🚀 **Async/Await Support**: Built with asyncio for non-blocking I/O operations
- 📊 **Multiple Data Types**: OHLCV data, trade information, and technical indicators
- 🔧 **Type Safety**: Full Pydantic model validation for all data structures
- 💾 **Export Capabilities**: JSON, CSV, and Parquet export formats
- ⚡ **Real-time Processing**: Stream processing with minimal latency
- 🛡️ **Error Handling**: Comprehensive exception handling and recovery
- 📈 **Multiple Symbols**: Support for streaming multiple trading pairs
- 🔄 **Auto-retry Logic**: Built-in connection recovery and retry mechanisms

## Quick Start

### Basic Usage

```python
import asyncio
from tvkit.api.chart.realtime import RealtimeStreamer
from tvkit.api.chart.models import StreamConfig

async def basic_streaming():
    config = StreamConfig(
        symbols=["BINANCE:BTCUSDT", "NASDAQ:AAPL"],
        timeframe="1m",
        num_candles=50
    )

    async with RealtimeStreamer(config) as streamer:
        async for response in streamer.stream():
            if response.data_type == 'ohlcv' and response.ohlcv_data:
                latest = response.ohlcv_data[-1]
                print(f"{response.symbol}: {latest.close}")

asyncio.run(basic_streaming())
```

## Configuration Classes

#### `ExportConfig`

Configuration for data export functionality.

```python
export_config = ExportConfig(
    export_result=True,  # Enable/disable export
    export_type='json'   # 'json' or 'csv'
)
```

#### `StreamConfig`

Configuration for WebSocket streaming.

```python
stream_config = StreamConfig(
    websocket_jwt_token="unauthorized_user_token",
    timeframe='1m',           # '1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1M'
    numb_price_candles=10     # Number of candles to retrieve (1-1000)
)
```

#### `IndicatorConfig`

Configuration for technical indicators.

```python
indicator_config = IndicatorConfig(
    indicator_id="RSI@tv-basicstudies",  # Indicator ID (optional)
    indicator_version="1"                # Indicator version (optional)
)
```

### Data Models

#### `OHLCData`

Model for OHLC (Open, High, Low, Close) data.

```python
{
    "index": 0,
    "timestamp": 1640995200.0,
    "open": 47150.0,
    "high": 47200.0,
    "low": 47100.0,
    "close": 47180.0,
    "volume": 1500.0
}
```

#### `IndicatorData`

Model for technical indicator data.

```python
{
    "index": 0,
    "timestamp": 1640995200.0,
    "smoothing": 65.5,
    "close": 47180.0
}
```

#### `StreamData`

Combined model containing both OHLC and indicator data.

```python
{
    "ohlc": [OHLCData, ...],
    "indicator": [IndicatorData, ...]
}
```

### Main Class

#### `RealtimeStreamer`

Async class to handle streaming of real-time market data from TradingView.

## Usage Examples

### Basic Real-time Streaming

```python
import asyncio
from tvkit.api.chart.realtime import RealtimeStreamer, ExportConfig, StreamConfig

async def basic_streaming():
    export_config = ExportConfig(export_result=False)
    stream_config = StreamConfig(timeframe='1m', numb_price_candles=10)

    async with RealtimeStreamer(
        export_config=export_config,
        stream_config=stream_config
    ) as streamer:
        result = await streamer.stream(exchange="BINANCE", symbol="BTCUSDT")

        # result is an async generator when export_result=False
        if hasattr(result, '__aiter__'):
            async for packet in result:
                print(packet)
                break  # Show first packet

asyncio.run(basic_streaming())
```

### Streaming with Export

```python
import asyncio
from tvkit.api.chart.realtime import RealtimeStreamer, ExportConfig, StreamConfig, StreamData

async def export_streaming():
    export_config = ExportConfig(export_result=True, export_type='json')
    stream_config = StreamConfig(timeframe='5m', numb_price_candles=20)

    async with RealtimeStreamer(
        export_config=export_config,
        stream_config=stream_config
    ) as streamer:
        result = await streamer.stream(exchange="BINANCE", symbol="ETHUSDT")

        # result is a StreamData object when export_result=True
        if isinstance(result, StreamData):
            print(f"OHLC data points: {len(result.ohlc)}")
            print(f"Indicator data points: {len(result.indicator)}")

asyncio.run(export_streaming())
```

### Streaming with Technical Indicators

```python
import asyncio
from tvkit.api.chart.realtime import (
    RealtimeStreamer, ExportConfig, StreamConfig, IndicatorConfig
)

async def indicator_streaming():
    export_config = ExportConfig(export_result=True, export_type='json')
    stream_config = StreamConfig(timeframe='1m', numb_price_candles=30)
    indicator_config = IndicatorConfig(
        indicator_id="RSI@tv-basicstudies",
        indicator_version="1"
    )

    async with RealtimeStreamer(
        export_config=export_config,
        stream_config=stream_config,
        indicator_config=indicator_config
    ) as streamer:
        result = await streamer.stream(exchange="NASDAQ", symbol="AAPL")

        if isinstance(result, StreamData):
            print(f"OHLC data: {len(result.ohlc)} points")
            print(f"Indicator data: {len(result.indicator)} points")

asyncio.run(indicator_streaming())
```

### Symbol Validation

```python
import asyncio
from tvkit.api.chart.realtime import RealtimeStreamer

async def validate_symbols():
    streamer = RealtimeStreamer()

    try:
        # Validate single symbol
        is_valid = await streamer.validate_symbols("BINANCE:BTCUSDT")
        print(f"Single symbol valid: {is_valid}")

        # Validate multiple symbols
        symbols = ["BINANCE:BTCUSDT", "NASDAQ:AAPL", "NYSE:TSLA"]
        is_valid = await streamer.validate_symbols(symbols)
        print(f"Multiple symbols valid: {is_valid}")

    except ValueError as e:
        print(f"Validation error: {e}")

asyncio.run(validate_symbols())
```

## Key Differences from Original Streamer

1. **Async/Await**: Full async implementation instead of synchronous blocking calls
2. **Pydantic Models**: Type-safe configuration and data models
3. **Context Manager**: Proper resource management with async context managers
4. **Error Handling**: Improved error handling with custom exceptions
5. **Symbol Validation**: Async symbol validation with retry logic
6. **WebSocket Management**: Better WebSocket connection lifecycle management

## Configuration Options

### Timeframes

Supported timeframes: `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`, `1w`, `1M`

### Export Types

- `json`: Export data as JSON files
- `csv`: Export data as CSV files

### WebSocket Authentication

The module uses JWT tokens for WebSocket authentication. The default token `"unauthorized_user_token"` works for public data.

## Error Handling

The module includes comprehensive error handling:

- `DataNotFoundError`: When expected data is not found in the stream
- `ValueError`: For invalid symbols or configuration
- `ConnectionClosed`: When WebSocket connection is lost
- `WebSocketException`: For WebSocket-related errors

## Dependencies

- `pydantic>=2.11.7`: For data validation and settings management
- `websockets>=13.0`: For async WebSocket communication
- `httpx>=0.28.0`: For async HTTP requests (symbol validation)
- `asyncio`: Built-in async support

## Export Files

When `export_result=True`, data files are saved to an `export/` directory with the following naming convention:

```
export/
├── ohlc_btcusdt_1m_20240101-123045.json
├── indicator_btcusdt_1m_20240101-123045.json
├── ohlc_ethusdt_5m_20240101-123100.csv
└── indicator_ethusdt_5m_20240101-123100.csv
```

The filename format is: `{data_category}_{symbol}_{timeframe}_{timestamp}.{extension}`

## Notes

- This module requires Python 3.8+ for async/await support
- WebSocket connections are automatically managed and closed properly
- Symbol validation includes retry logic for network resilience
- The module is designed to be a drop-in replacement for the original `streamer.py` with enhanced async capabilities
