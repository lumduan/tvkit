# ConnectionService Documentation

## Overview

The `ConnectionService` is a core component of tvkit's real-time chart API that manages WebSocket connections and TradingView sessions for streaming financial data. This service handles low-level WebSocket connection management, session initialization, and symbol subscription for TradingView data streams.

**Module Path**: `tvkit.api.chart.services.connection_service`

## Architecture

The ConnectionService follows the async-first architecture pattern used throughout tvkit:

- **Async WebSocket Management**: Uses the `websockets` library for async WebSocket operations
- **Session Management**: Handles both quote and chart sessions required by TradingView's protocol
- **Type Safety**: Uses Pydantic models for configuration and type validation
- **Error Handling**: Implements comprehensive error handling with proper logging
- **Resource Management**: Provides context-safe connection lifecycle management

## Class Definition

### ConnectionService

```python
class ConnectionService:
    """
    Service for managing WebSocket connections and TradingView sessions.

    This service handles the low-level WebSocket connection management,
    session initialization, and symbol subscription for TradingView data streams.
    """
```

#### Constructor

```python
def __init__(self, ws_url: str) -> None
```

**Description**: Initialize the connection service with a WebSocket URL.

**Parameters**:
- `ws_url` (str): The WebSocket URL for TradingView data streaming

**Attributes**:
- `ws_url` (str): Stored WebSocket URL
- `ws` (ClientConnection): WebSocket client connection instance

## Methods

### Connection Management

#### connect()

```python
async def connect(self) -> None
```

**Description**: Establishes the WebSocket connection to TradingView with proper headers and configuration.

**Implementation Details**:
- Creates browser-like request headers to mimic legitimate client behavior
- Configures WebSocket parameters including compression, ping intervals, and timeouts
- Uses Pydantic models for type-safe configuration
- Implements comprehensive error handling and logging

**Configuration**:
- **Accept-Encoding**: `gzip, deflate, br, zstd`
- **Origin**: `https://www.tradingview.com`
- **User-Agent**: Chrome browser simulation
- **Compression**: `deflate`
- **Ping Interval**: 20 seconds
- **Ping/Close Timeout**: 10 seconds each

**Raises**:
- `WebSocketException`: If connection establishment fails
- Generic `Exception`: For any other connection-related errors

**Usage Example**:
```python
service = ConnectionService("wss://data.tradingview.com/socket.io/websocket")
await service.connect()
```

#### close()

```python
async def close(self) -> None
```

**Description**: Safely closes the WebSocket connection.

**Implementation Details**:
- Checks for connection existence before attempting to close
- Handles graceful shutdown of WebSocket connection
- Safe to call multiple times or on unestablished connections

**Usage Example**:
```python
await service.close()
```

### Session Management

#### initialize_sessions()

```python
async def initialize_sessions(
    self,
    quote_session: str,
    chart_session: str,
    send_message_func: Callable[[str, list[Any]], Awaitable[None]],
) -> None
```

**Description**: Initializes the WebSocket sessions for quotes and charts using TradingView's protocol.

**Parameters**:
- `quote_session` (str): The quote session identifier
- `chart_session` (str): The chart session identifier
- `send_message_func` (Callable): Function to send messages through the WebSocket

**Protocol Messages Sent**:
1. `set_auth_token`: Authenticates with unauthorized user token
2. `set_locale`: Sets language to English (US)
3. `chart_create_session`: Creates chart session for OHLCV data
4. `quote_create_session`: Creates quote session for real-time price data
5. `quote_set_fields`: Configures quote data fields (28+ fields)
6. `quote_hibernate_all`: Optimizes quote session for selective updates

**Usage Example**:
```python
async def send_message(method: str, params: list[Any]) -> None:
    # Implementation of message sending
    pass

await service.initialize_sessions("quote_1", "chart_1", send_message)
```

#### _get_quote_fields()

```python
def _get_quote_fields(self) -> list[str]
```

**Description**: Returns the comprehensive list of fields for the quote session.

**Returns**: List of 28+ quote field identifiers including:

**Price & Change Data**:
- `ch`: Change amount
- `chp`: Change percentage
- `lp`: Last price
- `lp_time`: Last price timestamp

**Symbol Information**:
- `description`: Full symbol description
- `local_description`: Localized description
- `original_name`: Original symbol name
- `pro_name`: Professional symbol name
- `short_name`: Short symbol name

**Market Data**:
- `exchange`: Exchange identifier
- `currency_code`: Trading currency
- `volume`: Trading volume
- `current_session`: Current trading session

**Technical Details**:
- `fractional`: Fractional pricing support
- `minmov`: Minimum movement
- `minmove2`: Secondary minimum movement
- `pricescale`: Price scaling factor
- `update_mode`: Update frequency mode

### Symbol Management

#### add_symbol_to_sessions()

```python
async def add_symbol_to_sessions(
    self,
    quote_session: str,
    chart_session: str,
    exchange_symbol: str,
    timeframe: str,
    bars_count: int,
    send_message_func: Callable[[str, list[Any]], Awaitable[None]],
) -> None
```

**Description**: Adds a symbol to both quote and chart sessions for comprehensive data streaming.

**Parameters**:
- `quote_session` (str): Quote session identifier
- `chart_session` (str): Chart session identifier
- `exchange_symbol` (str): Symbol in 'EXCHANGE:SYMBOL' format (e.g., "NASDAQ:AAPL")
- `timeframe` (str): Chart timeframe ("1", "5", "15", "30", "60", "240", "D", "W", "M")
- `bars_count` (int): Number of historical bars to fetch
- `send_message_func` (Callable): Message sending function

**Protocol Operations**:
1. **Symbol Resolution**: Creates JSON configuration with splits adjustment
2. **Quote Subscription**: Adds symbol to quote session for real-time price updates
3. **Chart Resolution**: Resolves symbol for chart data (sds_sym_1)
4. **Series Creation**: Creates chart series for OHLCV data (sds_1)
5. **Fast Symbols**: Enables fast price updates for the symbol
6. **Volume Study**: Adds volume analysis study (20-period)
7. **Hibernation**: Optimizes quote session for selective updates

**Symbol Format**: Uses TradingView's format: `EXCHANGE:SYMBOL`
- Examples: `"NASDAQ:AAPL"`, `"BINANCE:BTCUSDT"`, `"FOREX:EURUSD"`

**Usage Example**:
```python
await service.add_symbol_to_sessions(
    "quote_1",
    "chart_1",
    "NASDAQ:AAPL",
    "1D",
    100,
    send_message
)
```

#### add_multiple_symbols_to_sessions()

```python
async def add_multiple_symbols_to_sessions(
    self,
    quote_session: str,
    exchange_symbols: List[str],
    send_message_func: Callable[[str, list[Any]], Awaitable[None]],
) -> None
```

**Description**: Efficiently adds multiple symbols to the quote session for batch real-time data streaming.

**Parameters**:
- `quote_session` (str): Quote session identifier
- `exchange_symbols` (List[str]): List of symbols in 'EXCHANGE:SYMBOL' format
- `send_message_func` (Callable): Message sending function

**Implementation Details**:
- Uses the first symbol as a template for session configuration
- Configures USD currency and regular trading session by default
- Performs batch symbol addition for optimal performance
- Enables fast symbol updates for all symbols simultaneously

**Configuration**:
- **Currency**: USD (default)
- **Session**: Regular trading hours
- **Adjustment**: Stock splits included

**Usage Example**:
```python
symbols = ["NASDAQ:AAPL", "NASDAQ:GOOGL", "NASDAQ:MSFT"]
await service.add_multiple_symbols_to_sessions("quote_1", symbols, send_message)
```

### Data Streaming

#### get_data_stream()

```python
async def get_data_stream(self) -> AsyncGenerator[dict[str, Any], None]
```

**Description**: Continuously receives and processes data from the TradingView server via WebSocket connection.

**Returns**: AsyncGenerator yielding parsed JSON data dictionaries

**Data Processing**:
1. **Message Handling**: Processes WebSocket messages (str, bytes, memoryview)
2. **Heartbeat Detection**: Identifies and responds to server heartbeats automatically
3. **Message Parsing**: Splits TradingView's custom message format (`~m~<length>~m~<data>`)
4. **JSON Parsing**: Converts message data to Python dictionaries
5. **Error Recovery**: Handles parsing errors gracefully with logging

**Message Types Handled**:
- **Heartbeat Messages**: Pattern `~m~\d+~m~~h~\d+$` - echoed back to server
- **Data Messages**: JSON-formatted market data, quotes, and chart updates
- **Error Messages**: Connection and protocol errors

**Error Handling**:
- `ConnectionClosed`: WebSocket connection terminated
- `WebSocketException`: WebSocket protocol errors
- `json.JSONDecodeError`: Invalid JSON message format
- Generic exceptions for unexpected errors

**Raises**:
- `RuntimeError`: If WebSocket connection is not established

**Usage Example**:
```python
async for data in service.get_data_stream():
    if "m" in data:  # Market data message
        print(f"Received market data: {data}")
    elif "p" in data:  # Price update
        print(f"Price update: {data}")
```

## Integration Points

### Dependencies

**Core Dependencies**:
- `websockets`: Async WebSocket client library
- `json`: JSON parsing and serialization
- `logging`: Structured logging for debugging and monitoring
- `typing`: Type annotations for code safety

**Internal Dependencies**:
- `tvkit.api.chart.models.realtime.ExtraRequestHeader`: HTTP headers model
- `tvkit.api.chart.models.realtime.WebSocketConnection`: WebSocket configuration model

### Related Components

**Message Service**: Works with `MessageService` for message formatting and protocol handling
**OHLCV Client**: Used by the main `OHLCV` client for data streaming
**Realtime Models**: Uses Pydantic models for type-safe configuration

## Error Handling Patterns

### Connection Errors
```python
try:
    await service.connect()
except WebSocketException as e:
    logging.error(f"WebSocket connection failed: {e}")
    # Implement retry logic or fallback
```

### Streaming Errors
```python
try:
    async for data in service.get_data_stream():
        process_data(data)
except ConnectionClosed:
    logging.error("Connection lost, attempting reconnection...")
    # Implement reconnection logic
```

### Resource Cleanup
```python
try:
    # Use connection service
    pass
finally:
    await service.close()  # Always cleanup
```

## Performance Considerations

### Connection Management
- **Keep-Alive**: Automatic ping/pong heartbeat (20-second intervals)
- **Compression**: Deflate compression reduces bandwidth usage
- **Connection Pooling**: Reuse connections for multiple symbols when possible

### Data Processing
- **Streaming**: Uses async generators for memory-efficient data processing
- **Batch Operations**: `add_multiple_symbols_to_sessions()` for bulk symbol subscription
- **Selective Updates**: Quote hibernation optimizes bandwidth usage

### Resource Usage
- **Memory**: Minimal memory footprint with streaming data processing
- **CPU**: Efficient JSON parsing with error handling
- **Network**: Optimized WebSocket configuration with compression

## Security Considerations

### Authentication
- Uses TradingView's "unauthorized_user_token" for public market data access
- No credentials required for basic market data streaming
- Headers mimic legitimate browser behavior

### Data Privacy
- No personal or sensitive data transmitted
- Public market data only
- WebSocket connections use TLS encryption (wss://)

## Troubleshooting

### Common Issues

**Connection Failures**:
- Verify WebSocket URL accessibility
- Check network connectivity and firewall settings
- Ensure proper SSL/TLS certificate handling

**Session Initialization Errors**:
- Verify session identifiers are unique and properly formatted
- Check message sending function implementation
- Monitor server response for initialization confirmation

**Data Stream Issues**:
- Implement proper error handling for connection drops
- Add retry logic with exponential backoff
- Monitor heartbeat responses for connection health

### Debugging Tips

**Enable Logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Monitor WebSocket Messages**:
```python
# Add debug logging to track all messages
async for data in service.get_data_stream():
    logging.debug(f"Received: {data}")
```

**Connection Health Checks**:
```python
# Monitor connection status
if hasattr(service, 'ws') and service.ws:
    print(f"Connection state: {service.ws.state}")
```

## Usage Examples

### Basic Connection and Streaming

```python
import asyncio
from tvkit.api.chart.services.connection_service import ConnectionService

async def basic_streaming():
    service = ConnectionService("wss://data.tradingview.com/socket.io/websocket")

    try:
        # Establish connection
        await service.connect()

        # Initialize sessions
        quote_session = "quote_1"
        chart_session = "chart_1"

        async def send_message(method: str, params: list) -> None:
            # Message sending implementation
            message = json.dumps({"method": method, "params": params})
            await service.ws.send(f"~m~{len(message)}~m~{message}")

        await service.initialize_sessions(quote_session, chart_session, send_message)

        # Add symbol for streaming
        await service.add_symbol_to_sessions(
            quote_session, chart_session, "NASDAQ:AAPL", "1D", 100, send_message
        )

        # Stream data
        async for data in service.get_data_stream():
            print(f"Market data: {data}")
            break  # Exit after first message for demo

    finally:
        await service.close()

# Run the example
asyncio.run(basic_streaming())
```

### Multiple Symbol Monitoring

```python
async def monitor_portfolio():
    service = ConnectionService("wss://data.tradingview.com/socket.io/websocket")

    symbols = [
        "NASDAQ:AAPL",    # Apple Inc.
        "NASDAQ:GOOGL",   # Alphabet Inc.
        "NASDAQ:MSFT",    # Microsoft Corp.
        "BINANCE:BTCUSDT" # Bitcoin
    ]

    try:
        await service.connect()

        quote_session = "quote_1"

        async def send_message(method: str, params: list) -> None:
            message = json.dumps({"method": method, "params": params})
            await service.ws.send(f"~m~{len(message)}~m~{message}")

        # Initialize quote session only (no charts needed)
        await send_message("set_auth_token", ["unauthorized_user_token"])
        await send_message("quote_create_session", [quote_session])
        await send_message("quote_set_fields", [quote_session, *service._get_quote_fields()])

        # Add multiple symbols
        await service.add_multiple_symbols_to_sessions(
            quote_session, symbols, send_message
        )

        # Process real-time updates
        async for data in service.get_data_stream():
            if "p" in data:  # Price update message
                symbol = data.get("p", [{}])[1].get("s")  # Extract symbol
                price = data.get("p", [{}])[1].get("lp")  # Extract last price
                if symbol and price:
                    print(f"{symbol}: ${price}")

    finally:
        await service.close()

asyncio.run(monitor_portfolio())
```

### Error Handling and Reconnection

```python
async def robust_streaming_with_reconnection():
    max_retries = 5
    retry_delay = 1  # Start with 1 second delay

    for attempt in range(max_retries):
        service = ConnectionService("wss://data.tradingview.com/socket.io/websocket")

        try:
            await service.connect()

            # Your streaming logic here
            async for data in service.get_data_stream():
                print(f"Data: {data}")

        except (ConnectionClosed, WebSocketException) as e:
            logging.warning(f"Connection error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                logging.error("Max retries reached, giving up")
                break

        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            break

        finally:
            await service.close()

asyncio.run(robust_streaming_with_reconnection())
```

## API Reference Summary

### Constructor
- `__init__(ws_url: str)`: Initialize service with WebSocket URL

### Connection Methods
- `connect()`: Establish WebSocket connection
- `close()`: Close WebSocket connection

### Session Methods
- `initialize_sessions(quote_session, chart_session, send_message_func)`: Initialize TradingView sessions
- `_get_quote_fields()`: Get quote field configuration

### Symbol Methods
- `add_symbol_to_sessions(quote_session, chart_session, exchange_symbol, timeframe, bars_count, send_message_func)`: Add single symbol
- `add_multiple_symbols_to_sessions(quote_session, exchange_symbols, send_message_func)`: Add multiple symbols

### Streaming Methods
- `get_data_stream()`: Get async data stream generator

---

**Note**: This documentation reflects tvkit v0.1.4. The ConnectionService is a low-level component typically used through higher-level clients like the OHLCV class. For typical usage, see the main tvkit documentation and examples.