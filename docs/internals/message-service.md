# Message Service Internals

`MessageService` handles the construction, framing, and transmission of all outgoing WebSocket messages. It implements TradingView's custom wire format and provides session identifier generation. It is a low-level internal component; most application code should use the `OHLCV` context manager instead.

**Module**: `tvkit.api.chart.services.message_service`

## Responsibilities

| Responsibility | Method |
|----------------|--------|
| Generate session identifiers | `generate_session()` |
| Add TradingView framing header | `prepend_header()` |
| Serialize a message to JSON | `construct_message()` |
| Frame and serialize in one step | `create_message()` |
| Send a message over the socket | `send_message()` |
| Return a sendable callable | `get_send_message_callable()` |

`MessageService` holds a reference to the active `ClientConnection` (`self.ws`). It does not own the connection — `ConnectionService` owns it and passes the reference at construction time.

## Message Pipeline

Every outgoing message passes through this pipeline:

```text
(func, args)
      │
      ▼
construct_message()
  → {"m": func, "p": args}  (compact JSON, no spaces)
      │
      ▼
prepend_header()
  → ~m~<byte_length>~m~<json_payload>
      │
      ▼
ws.send()   (async WebSocket transmission)
```

`send_message()` runs all three steps in sequence. `create_message()` runs the first two and returns the fully framed WebSocket payload string without sending it — useful for testing or manual inspection.

## Wire Format

TradingView's protocol wraps every JSON payload in a length-prefixed frame:

```text
~m~<length>~m~<payload>
```

- `~m~` is a fixed delimiter
- `<length>` is the **byte length** of `<payload>` as a decimal integer
- `<payload>` is the compact JSON body

`prepend_header()` computes the byte length of the UTF-8 encoded payload (not the Python string character count) before building the frame. This distinction matters for non-ASCII content, though in practice TradingView messages are ASCII-only.

Example of a fully framed message:

```text
~m~52~m~{"m":"set_auth_token","p":["unauthorized_user_token"]}
```

Multiple frames may be concatenated into a single WebSocket transmission — the receiver uses the length field to split them. tvkit currently sends messages individually for clarity. See [Message Framing](../architecture/websocket-protocol.md#message-framing) for the full protocol description.

> **Note**: Heartbeat responses (`~h~N`) are handled by `ConnectionService` and bypass `MessageService` entirely — they are echoed back as raw strings without going through the message pipeline.

## JSON Message Structure

`construct_message()` produces compact JSON following TradingView's required shape:

```json
{"m": "function_name", "p": ["param1", "param2"]}
```

- `"m"` — the method name (e.g., `set_auth_token`, `create_series`)
- `"p"` — the parameter array; elements may be strings, integers, or nested objects

Compact serialization (no spaces) matches the format used by TradingView's own client and slightly reduces frame size.

## Session Generation

`generate_session()` produces identifiers like `cs_abcdefghijkl` or `qs_mnopqrstuvwx`:

```python
def generate_session(self, prefix: str) -> str:
    # 12 random lowercase letters via secrets.choice
    # e.g., generate_session("cs_") → "cs_xkqmztpnjfab"
```

The `secrets` module is used for high-quality randomness. Sessions are scoped to the WebSocket connection lifetime — they are not reused across reconnections.

TradingView session prefixes used by tvkit:

| Prefix | Session type |
|--------|-------------|
| `cs_` | Chart session — used for OHLCV series and symbol resolution |
| `qs_` | Quote session — used for real-time price and quote field updates |

## Callable Injection

`get_send_message_callable()` returns `self.send_message` as a bound method reference. This is the mechanism that keeps `ConnectionService` decoupled from `MessageService`:

```python
send_func = message_service.get_send_message_callable()
# send_func has signature: async (func: str, args: list[Any]) -> None

await connection_service.initialize_sessions(
    quote_session, chart_session, send_func
)
```

`ConnectionService` accepts any callable with that signature — it does not import or reference `MessageService` directly. This makes both services independently testable: replace `send_func` with a mock to capture outgoing messages without an active WebSocket.

## Error Handling

| Error | Condition | Handling |
|-------|-----------|----------|
| `RuntimeError` | `send_message()` called before `connect()` | Raised immediately |
| `ConnectionClosed` | Socket closed during `ws.send()` | Propagates to caller |
| `WebSocketException` | Protocol-level transmission failure | Propagates to caller |

Outgoing messages are logged at DEBUG level using the library logger before each transmission. To inspect the full message sequence during development:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Relationship with ConnectionService

The two services divide protocol responsibilities as follows:

| Concern | Owner |
|---------|-------|
| Socket lifecycle (open/close) | `ConnectionService` |
| Incoming message parsing | `ConnectionService` |
| Heartbeat echo | `ConnectionService` |
| Outgoing message framing | `MessageService` |
| Session identifier generation | `MessageService` |
| Protocol message sequencing | `ConnectionService` (calls `send_func`) |

`ConnectionService` orchestrates the session sequence; `MessageService` handles the encoding and transmission of each individual message.

## See Also

- [Connection Service](connection-service.md) — session management and incoming message handling
- [WebSocket Protocol](../architecture/websocket-protocol.md) — wire format and full message reference
- [OHLCV Client](../api/chart/ohlcv.md) — the public interface that uses both services
