# MessageService Documentation

## Overview

The `MessageService` is a core component of tvkit's real-time chart API that handles the construction, formatting, and transmission of WebSocket messages to TradingView's servers. This service implements TradingView's custom WebSocket protocol for reliable communication and provides a clean abstraction layer for message handling.

**Module Path**: `tvkit.api.chart.services.message_service`

## Architecture

The MessageService follows tvkit's async-first architecture and provides:

- **Protocol Implementation**: Handles TradingView's custom WebSocket message format
- **Message Construction**: Creates properly formatted JSON messages with protocol headers
- **Session Management**: Generates secure session identifiers for connection tracking
- **Error Handling**: Comprehensive error handling with proper exception propagation
- **Type Safety**: Full type annotations and parameter validation
- **Logging Integration**: Detailed logging for debugging and monitoring

## Class Definition

### MessageService

```python
class MessageService:
    """
    Service for constructing and sending WebSocket messages to TradingView.

    This service handles the message protocol, formatting, and sending
    operations for TradingView WebSocket communication.
    """
```

#### Constructor

```python
def __init__(self, ws: ClientConnection) -> None
```

**Description**: Initialize the message service with an active WebSocket connection.

**Parameters**:
- `ws` (ClientConnection): The WebSocket connection to use for sending messages

**Attributes**:
- `ws` (ClientConnection): Stored WebSocket connection for message transmission

## Methods

### Session Management

#### generate_session()

```python
def generate_session(self, prefix: str) -> str
```

**Description**: Generates a cryptographically secure session identifier for TradingView connections.

**Parameters**:
- `prefix` (str): The prefix to prepend to the random string (e.g., "quote_", "chart_")

**Returns**:
- `str`: A session identifier consisting of the prefix and a 12-character random string

**Implementation Details**:
- Uses `secrets` module for cryptographically secure randomness
- Generates 12 lowercase letters for the random component
- Ensures session uniqueness across concurrent connections

**Security Notes**:
- Uses cryptographically secure random number generation
- Session identifiers are unpredictable and collision-resistant
- Suitable for production environments with multiple concurrent sessions

**Usage Examples**:
```python
service = MessageService(websocket_connection)

# Generate session identifiers for different purposes
quote_session = service.generate_session("quote_")     # e.g., "quote_abcdefghijkl"
chart_session = service.generate_session("chart_")     # e.g., "chart_mnopqrstuvwx"
custom_session = service.generate_session("custom_")   # e.g., "custom_yzabcdefghij"
```

### Message Protocol Handling

#### prepend_header()

```python
def prepend_header(self, message: str) -> str
```

**Description**: Prepends TradingView's custom protocol header indicating message length.

**Parameters**:
- `message` (str): The message content to be wrapped with protocol header

**Returns**:
- `str`: The message prefixed with TradingView's length header format

**Protocol Format**: `~m~{length}~m~{message}`
- `~m~`: Protocol delimiter markers
- `{length}`: Byte length of the message content
- `{message}`: The actual message content

**Implementation Details**:
- Calculates exact byte length of the message
- Wraps message with TradingView's expected protocol format
- Essential for proper message parsing on the server side

**Usage Examples**:
```python
# Protocol header formatting
raw_message = '{"m":"quote_create_session","p":["quote_12345"]}'
formatted_message = service.prepend_header(raw_message)
# Result: "~m~49~m~{"m":"quote_create_session","p":["quote_12345"]}"

# Length calculation is automatic
short_msg = service.prepend_header("test")  # "~m~4~m~test"
long_msg = service.prepend_header("a" * 100)  # "~m~100~m~{100 'a' characters}"
```

#### construct_message()

```python
def construct_message(self, func: str, param_list: list[Any]) -> str
```

**Description**: Constructs a JSON message following TradingView's WebSocket protocol structure.

**Parameters**:
- `func` (str): The TradingView function/method name to call
- `param_list` (list[Any]): List of parameters for the function call

**Returns**:
- `str`: JSON-formatted message with compact serialization

**Message Structure**:
```json
{
  "m": "function_name",
  "p": ["param1", "param2", "param3"]
}
```

**Implementation Details**:
- Uses compact JSON serialization (no spaces) for efficiency
- Follows TradingView's exact protocol requirements
- Handles various parameter types (strings, numbers, objects, arrays)

**Supported Function Types**:
- **Authentication**: `set_auth_token`, `set_locale`
- **Session Management**: `quote_create_session`, `chart_create_session`
- **Symbol Operations**: `quote_add_symbols`, `resolve_symbol`, `create_series`
- **Configuration**: `quote_set_fields`, `quote_hibernate_all`
- **Studies**: `create_study` (technical analysis)

**Usage Examples**:
```python
# Authentication message
auth_msg = service.construct_message("set_auth_token", ["unauthorized_user_token"])
# Result: '{"m":"set_auth_token","p":["unauthorized_user_token"]}'

# Session creation
session_msg = service.construct_message("quote_create_session", ["quote_abc123"])
# Result: '{"m":"quote_create_session","p":["quote_abc123"]}'

# Symbol addition with complex parameters
symbol_msg = service.construct_message("quote_add_symbols",
    ["quote_abc123", "NASDAQ:AAPL", "NASDAQ:GOOGL"])
# Result: '{"m":"quote_add_symbols","p":["quote_abc123","NASDAQ:AAPL","NASDAQ:GOOGL"]}'
```

#### create_message()

```python
def create_message(self, func: str, param_list: list[Any]) -> str
```

**Description**: Creates a complete, protocol-ready message by combining JSON construction with header formatting.

**Parameters**:
- `func` (str): The TradingView function name
- `param_list` (list[Any]): Function parameters

**Returns**:
- `str`: Complete message ready for WebSocket transmission

**Process Flow**:
1. Constructs JSON message using `construct_message()`
2. Adds protocol header using `prepend_header()`
3. Returns transmission-ready message

**Usage Examples**:
```python
# Complete message creation in one step
complete_msg = service.create_message("set_locale", ["en", "US"])
# Result: "~m~36~m~{"m":"set_locale","p":["en","US"]}"

# Chart session creation
chart_msg = service.create_message("chart_create_session", ["chart_xyz789", ""])
# Result: "~m~48~m~{"m":"chart_create_session","p":["chart_xyz789",""]}"
```

### Message Transmission

#### send_message()

```python
async def send_message(self, func: str, args: list[Any]) -> None
```

**Description**: Sends a complete message to the TradingView WebSocket server with comprehensive error handling.

**Parameters**:
- `func` (str): The TradingView function name to call
- `args` (list[Any]): Arguments for the function

**Returns**: None

**Error Handling**:
- **Connection Validation**: Ensures WebSocket connection is established
- **Transmission Errors**: Handles connection drops and protocol errors
- **Logging**: Provides detailed debug and error logging

**Raises**:
- `RuntimeError`: If WebSocket connection is not established
- `ConnectionClosed`: If WebSocket connection is closed during send
- `WebSocketException`: If message transmission fails

**Implementation Details**:
- Creates complete message using `create_message()`
- Logs message content for debugging (debug level)
- Handles connection state validation
- Provides specific error messages for different failure modes

**Usage Examples**:
```python
try:
    # Send authentication
    await service.send_message("set_auth_token", ["unauthorized_user_token"])

    # Send session creation
    await service.send_message("quote_create_session", ["quote_session_1"])

    # Send symbol subscription
    await service.send_message("quote_add_symbols", ["quote_session_1", "NASDAQ:AAPL"])

except RuntimeError as e:
    print(f"Connection not established: {e}")
except ConnectionClosed as e:
    print(f"Connection lost: {e}")
    # Implement reconnection logic
except WebSocketException as e:
    print(f"Transmission failed: {e}")
    # Handle transmission errors
```

#### get_send_message_callable()

```python
def get_send_message_callable(self) -> Callable[[str, list[Any]], Awaitable[None]]
```

**Description**: Returns a callable reference to the `send_message` method for dependency injection and service composition.

**Returns**:
- `Callable[[str, list[Any]], Awaitable[None]]`: Async callable for message sending

**Use Cases**:
- **Service Composition**: Pass message sending capability to other services
- **Dependency Injection**: Decouple services from direct MessageService dependency
- **Testing**: Enable easy mocking of message sending functionality
- **Callbacks**: Use as callback function in event-driven architectures

**Usage Examples**:
```python
# Service composition with ConnectionService
connection_service = ConnectionService(websocket_url)
message_service = MessageService(connection_service.ws)

# Get callable reference
send_func = message_service.get_send_message_callable()

# Pass to ConnectionService for session initialization
await connection_service.initialize_sessions(
    quote_session="quote_123",
    chart_session="chart_456",
    send_message_func=send_func  # Injected dependency
)

# Use in other contexts
async def custom_operation(send_message):
    await send_message("custom_function", ["param1", "param2"])

await custom_operation(send_func)
```

## Integration Patterns

### With ConnectionService

The MessageService works closely with ConnectionService for complete WebSocket management:

```python
import asyncio
from tvkit.api.chart.services.connection_service import ConnectionService
from tvkit.api.chart.services.message_service import MessageService

async def integrated_example():
    # Establish connection
    connection_service = ConnectionService("wss://data.tradingview.com/socket.io/websocket")
    await connection_service.connect()

    # Create message service
    message_service = MessageService(connection_service.ws)

    # Generate sessions
    quote_session = message_service.generate_session("quote_")
    chart_session = message_service.generate_session("chart_")

    # Initialize sessions using message service
    await connection_service.initialize_sessions(
        quote_session,
        chart_session,
        message_service.get_send_message_callable()
    )

    # Add symbols
    await connection_service.add_symbol_to_sessions(
        quote_session,
        chart_session,
        "NASDAQ:AAPL",
        "1D",
        100,
        message_service.get_send_message_callable()
    )
```

### With OHLCV Client

MessageService is typically used internally by higher-level clients:

```python
# Internal usage within OHLCV client
class OHLCVClient:
    def __init__(self):
        self.connection_service = None
        self.message_service = None

    async def __aenter__(self):
        self.connection_service = ConnectionService(websocket_url)
        await self.connection_service.connect()

        self.message_service = MessageService(self.connection_service.ws)

        # Initialize sessions
        quote_session = self.message_service.generate_session("quote_")
        chart_session = self.message_service.generate_session("chart_")

        send_func = self.message_service.get_send_message_callable()
        await self.connection_service.initialize_sessions(
            quote_session, chart_session, send_func
        )

        return self
```

## Protocol Reference

### TradingView WebSocket Message Format

**Complete Message Structure**:
```
~m~{length}~m~{"m":"{function}","p":[{parameters}]}
```

**Components**:
- `~m~`: Protocol delimiter (fixed)
- `{length}`: Message content length in bytes
- `{"m":"{function}","p":[{parameters}]}`: JSON payload

**Example Message Breakdown**:
```
Original: {"m":"set_auth_token","p":["unauthorized_user_token"]}
Length: 51 bytes
Complete: ~m~51~m~{"m":"set_auth_token","p":["unauthorized_user_token"]}
```

### Common TradingView Functions

**Authentication Functions**:
```python
await service.send_message("set_auth_token", ["unauthorized_user_token"])
await service.send_message("set_locale", ["en", "US"])
```

**Session Management Functions**:
```python
await service.send_message("quote_create_session", [quote_session])
await service.send_message("chart_create_session", [chart_session, ""])
```

**Symbol Management Functions**:
```python
await service.send_message("quote_add_symbols", [quote_session, "NASDAQ:AAPL"])
await service.send_message("quote_fast_symbols", [quote_session, "NASDAQ:AAPL"])
await service.send_message("resolve_symbol", [chart_session, "sds_sym_1", "=NASDAQ:AAPL"])
```

**Configuration Functions**:
```python
await service.send_message("quote_set_fields", [quote_session, "lp", "ch", "chp"])
await service.send_message("quote_hibernate_all", [quote_session])
```

## Error Handling Patterns

### Connection Validation

```python
try:
    await message_service.send_message("test_function", ["param"])
except RuntimeError as e:
    logging.error("WebSocket not connected: %s", e)
    # Establish connection before retrying
    await connection_service.connect()
    message_service = MessageService(connection_service.ws)
```

### Connection Recovery

```python
async def send_with_retry(service, func, args, max_retries=3):
    for attempt in range(max_retries):
        try:
            await service.send_message(func, args)
            return  # Success
        except ConnectionClosed:
            if attempt < max_retries - 1:
                logging.warning(f"Connection lost, retrying... ({attempt + 1}/{max_retries})")
                # Implement reconnection logic here
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                logging.error("Max retries reached, giving up")
                raise
```

### Message Validation

```python
def validate_message_params(func: str, args: list) -> bool:
    """Validate message parameters before sending"""

    # Session-based functions need valid session ID
    if func in ["quote_add_symbols", "quote_set_fields"]:
        if not args or not isinstance(args[0], str):
            return False

    # Symbol functions need valid symbol format
    if "symbol" in func and len(args) > 1:
        symbol = args[1]
        if ":" not in symbol:  # Must be EXCHANGE:SYMBOL format
            return False

    return True

# Usage
if validate_message_params("quote_add_symbols", ["quote_123", "NASDAQ:AAPL"]):
    await service.send_message("quote_add_symbols", ["quote_123", "NASDAQ:AAPL"])
```

## Performance Considerations

### Message Optimization

**Compact JSON Serialization**:
- Uses minimal JSON format (no spaces)
- Reduces bandwidth usage for high-frequency messaging
- Maintains compatibility with TradingView servers

**Efficient Session Generation**:
- Uses `secrets` module for optimal randomness performance
- 12-character sessions provide good uniqueness vs. length trade-off
- Lowercase letters only for consistent URL encoding

**Connection Reuse**:
- Single MessageService instance per WebSocket connection
- Reuses connection for multiple message types
- Minimizes connection overhead

### Scalability Patterns

**Batch Operations**:
```python
# Send multiple messages efficiently
async def send_batch_messages(service, messages):
    for func, args in messages:
        await service.send_message(func, args)
        # Small delay to avoid overwhelming server
        await asyncio.sleep(0.01)

# Usage
batch = [
    ("quote_add_symbols", ["quote_123", "NASDAQ:AAPL"]),
    ("quote_add_symbols", ["quote_123", "NASDAQ:GOOGL"]),
    ("quote_add_symbols", ["quote_123", "NASDAQ:MSFT"]),
]
await send_batch_messages(message_service, batch)
```

**Connection Pooling**:
```python
class MessageServicePool:
    def __init__(self, connection_pool):
        self.services = [MessageService(conn) for conn in connection_pool]
        self.current = 0

    def get_service(self) -> MessageService:
        service = self.services[self.current]
        self.current = (self.current + 1) % len(self.services)
        return service
```

## Security Considerations

### Session Security

**Cryptographically Secure Sessions**:
- Uses `secrets` module for unpredictable session IDs
- 12-character random component provides 2^62 possible combinations
- Session IDs are not predictable or enumerable

**Session Isolation**:
- Each connection uses unique session identifiers
- Sessions are scoped to individual WebSocket connections
- No session reuse across different connections

### Message Security

**No Credential Transmission**:
- Uses TradingView's "unauthorized_user_token" for public data
- No sensitive credentials required for market data access
- All communication over secure WebSocket (wss://)

**Parameter Validation**:
- Type-safe parameter handling
- JSON serialization prevents injection attacks
- Protocol headers prevent message tampering

## Testing and Debugging

### Debug Logging

Enable detailed message logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# MessageService will log all outgoing messages
await service.send_message("test_function", ["param"])
# Logs: "Sending message: ~m~35~m~{"m":"test_function","p":["param"]}"
```

### Message Inspection

```python
# Inspect message construction without sending
message_content = service.construct_message("quote_create_session", ["quote_123"])
print(f"JSON: {message_content}")

complete_message = service.create_message("quote_create_session", ["quote_123"])
print(f"Complete: {complete_message}")
```

### Mock Testing

```python
from unittest.mock import AsyncMock, Mock

# Mock WebSocket connection
mock_ws = AsyncMock()
mock_ws.send = AsyncMock()

# Test message service
service = MessageService(mock_ws)
await service.send_message("test", ["param"])

# Verify message was sent
mock_ws.send.assert_called_once()
sent_message = mock_ws.send.call_args[0][0]
assert "test" in sent_message
```

## Usage Examples

### Basic Message Sending

```python
import asyncio
from websockets import connect
from tvkit.api.chart.services.message_service import MessageService

async def basic_messaging():
    # Establish WebSocket connection
    websocket = await connect("wss://data.tradingview.com/socket.io/websocket")

    try:
        # Create message service
        service = MessageService(websocket)

        # Generate session
        session_id = service.generate_session("demo_")
        print(f"Generated session: {session_id}")

        # Send authentication
        await service.send_message("set_auth_token", ["unauthorized_user_token"])
        await service.send_message("set_locale", ["en", "US"])

        # Create quote session
        await service.send_message("quote_create_session", [session_id])

        print("Messages sent successfully!")

    finally:
        await websocket.close()

asyncio.run(basic_messaging())
```

### Advanced Session Management

```python
async def advanced_session_management():
    websocket = await connect("wss://data.tradingview.com/socket.io/websocket")
    service = MessageService(websocket)

    try:
        # Create multiple sessions for different purposes
        quote_session = service.generate_session("quote_")
        chart_session = service.generate_session("chart_")
        study_session = service.generate_session("study_")

        # Initialize all sessions
        sessions_to_create = [
            ("quote_create_session", [quote_session]),
            ("chart_create_session", [chart_session, ""]),
        ]

        for func, args in sessions_to_create:
            await service.send_message(func, args)

        # Configure quote session with multiple symbols
        symbols = ["NASDAQ:AAPL", "NASDAQ:GOOGL", "NYSE:TSLA"]

        # Set quote fields
        quote_fields = ["lp", "ch", "chp", "volume", "description"]
        await service.send_message("quote_set_fields", [quote_session] + quote_fields)

        # Add symbols
        for symbol in symbols:
            await service.send_message("quote_add_symbols", [quote_session, symbol])
            await service.send_message("quote_fast_symbols", [quote_session, symbol])

        # Hibernate session for efficiency
        await service.send_message("quote_hibernate_all", [quote_session])

        print(f"Advanced session setup complete!")
        print(f"Quote session: {quote_session}")
        print(f"Chart session: {chart_session}")
        print(f"Symbols: {', '.join(symbols)}")

    finally:
        await websocket.close()

asyncio.run(advanced_session_management())
```

### Error Handling and Recovery

```python
async def robust_messaging_with_recovery():
    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        websocket = None
        try:
            websocket = await connect("wss://data.tradingview.com/socket.io/websocket")
            service = MessageService(websocket)

            # Critical message sequence
            await service.send_message("set_auth_token", ["unauthorized_user_token"])
            await service.send_message("set_locale", ["en", "US"])

            session_id = service.generate_session("robust_")
            await service.send_message("quote_create_session", [session_id])

            print("Robust messaging completed successfully!")
            break

        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed: {e}")

            if websocket:
                await websocket.close()

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print("Max retries reached, operation failed")
                raise

asyncio.run(robust_messaging_with_recovery())
```

## API Reference Summary

### Constructor
- `__init__(ws: ClientConnection)`: Initialize with WebSocket connection

### Session Methods
- `generate_session(prefix: str) -> str`: Generate secure session identifier

### Message Construction
- `prepend_header(message: str) -> str`: Add protocol header
- `construct_message(func: str, param_list: list[Any]) -> str`: Create JSON message
- `create_message(func: str, param_list: list[Any]) -> str`: Create complete message

### Message Transmission
- `send_message(func: str, args: list[Any]) -> None`: Send message to server
- `get_send_message_callable() -> Callable`: Get callable reference for dependency injection

## Related Components

**Core Dependencies**:
- `websockets.ClientConnection`: WebSocket connection management
- `json`: Message serialization
- `secrets`: Cryptographically secure session generation
- `logging`: Debug and error logging

**Integration Points**:
- **ConnectionService**: Uses MessageService for session initialization and symbol management
- **OHLCV Client**: Uses MessageService internally for WebSocket communication
- **Real-time Models**: Message payloads validated against Pydantic models

---

**Note**: This documentation reflects tvkit v0.1.4. The MessageService is a low-level component typically used through higher-level clients like the OHLCV class. For typical usage, see the main tvkit documentation and examples.