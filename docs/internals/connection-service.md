# Connection Service Internals

`ConnectionService` manages the full lifecycle of a TradingView WebSocket session: opening the connection, running the session initialization sequence, subscribing to symbols, and streaming server messages. It is a low-level internal component. Most application code should use the `OHLCV` context manager instead.

**Module**: `tvkit.api.chart.services.connection_service`

## Responsibilities

| Responsibility | Method |
|----------------|--------|
| Open WebSocket connection | `connect()` |
| Close WebSocket connection | `close()` |
| Run session init sequence | `initialize_sessions()` |
| Subscribe one symbol | `add_symbol_to_sessions()` |
| Subscribe multiple symbols | `add_multiple_symbols_to_sessions()` |
| Parse incoming messages | `get_data_stream()` |

`ConnectionService` owns the WebSocket socket object (`self.ws`). `MessageService` receives a reference to it at construction time — this is the only shared state between the two services.

## Connection Lifecycle

```text
connect()
    │  (socket open; session identifiers created during next step)
    ▼
initialize_sessions()
    │
    ▼
add_symbol_to_sessions()   ← may be called once or multiple times
    │
    ▼
get_data_stream()   ← async loop; yields one dict per message
    │
    ▼
close()
```

These steps represent the typical initialization order. `get_data_stream()` will not yield meaningful data until sessions and symbols are initialized.

## Connection Setup

`connect()` opens the WebSocket using browser-like headers to satisfy TradingView's connection requirements:

- `Origin: https://www.tradingview.com`
- `User-Agent`: a recent Chrome user agent string

Additional WebSocket parameters: deflate compression enabled, 20-second WebSocket-level ping interval (additional transport-layer keepalive; the TradingView protocol also uses its own `~h~` heartbeat messages for application-layer keepalive — see [Heartbeat Handling](../architecture/websocket-protocol.md#heartbeat-handling)).

The connection URL is always `wss://data.tradingview.com/socket.io/websocket`. TradingView's browser client appends query parameters (`?from=chart&date=...`), but these are optional — the protocol works without them.

## Session Initialization Sequence

`initialize_sessions()` sends the required protocol messages before any data can be requested. The sequence is fixed:

```text
set_auth_token         → authenticate (always "unauthorized_user_token" for public data)
set_locale             → set language to en-US
chart_create_session   → open chart session (cs_<random>)
quote_create_session   → open quote session (qs_<random>)
quote_set_fields       → declare which quote fields the server should return (28+ fields)
quote_hibernate_all    → reduce quote bandwidth until symbols are added
```

The method takes `send_message_func` as a parameter rather than calling `MessageService` directly. This keeps `ConnectionService` decoupled from `MessageService` — it only needs a callable that matches `Callable[[str, list[Any]], Awaitable[None]]`.

## Symbol Subscription

`add_symbol_to_sessions()` subscribes a single symbol to both the chart and quote sessions:

```text
quote_add_symbols      → subscribe to real-time quote updates
resolve_symbol         → bind the symbol to sds_sym_1 for the chart session
create_series          → request OHLCV data (see Range Mode section below)
quote_fast_symbols     → request high-frequency quote updates
quote_hibernate_all    → re-optimize after adding the new symbol
```

### Symbol Descriptor Format

The `resolve_symbol` parameter uses double-encoded JSON — the symbol descriptor is a JSON object serialized as a string, prefixed with `=`, and passed as one element in the protocol parameter array:

```python
# The descriptor is JSON-serialized and prefixed with "="
# TradingView requires the "=" prefix to distinguish descriptor strings from plain symbol names
symbol_descriptor = "=" + json.dumps({"symbol": exchange_symbol, "adjustment": "splits"})
# e.g., '={"symbol":"NASDAQ:AAPL","adjustment":"splits"}'
# This string becomes one element of the p array in the wire message
```

Without the `=` prefix, the server may reject the descriptor or return `symbol_error`. This double-encoding is a TradingView protocol quirk — see [WebSocket Protocol — Symbol Resolution](../architecture/websocket-protocol.md#symbol-resolution) for the full wire format.

### Series Identifiers

The series subscription uses three fixed identifiers:

| Identifier | Role |
|------------|------|
| `sds_1` | Server-side series data source ID — used in `create_series`, `modify_series`, and server responses |
| `s1` | Client-side series key — used to match `du` response payloads back to this series |
| `sds_sym_1` | Symbol alias — the name by which the chart session refers to the resolved symbol |

These are positional in the protocol message arrays. Swapping any of them breaks the subscription silently.

## Range Mode Protocol

When `get_historical_ohlcv()` is called with `start`/`end` date parameters, `add_symbol_to_sessions()` sends two consecutive messages instead of one:

```text
create_series   → bars_count = MAX_BARS_REQUEST (sentinel), range_param = ""
modify_series   → range_param = "r,<from_unix>:<to_unix>"
```

`create_series` initializes the server-side series subscription. In range mode, `bars_count` is set to `MAX_BARS_REQUEST` (5000) as a placeholder — the server replaces the count-based request with the specified range once `modify_series` arrives.

In count mode, `modify_series` is never sent. The server uses count-based behaviour when no range constraint follows.

**Parameter structures** (position matters — any swap breaks the protocol):

```python
# create_series — 7 elements; trailing "" always required
[chart_session, "sds_1", "s1", "sds_sym_1", timeframe, bars_count, ""]

# modify_series — 6 elements; no trailing ""
[chart_session, "sds_1", "s1", "sds_sym_1", timeframe, "r,<from_unix>:<to_unix>"]
```

## Message Stream Parser

`get_data_stream()` is an async generator that yields one parsed dict per TradingView message. The processing pipeline:

```text
WebSocket frame (str / bytes / memoryview)
        │
        ▼
Heartbeat check  ─── matches ~m~\d+~m~~h~\d+ ──▶  echo back to server, skip
        │
        ▼  (non-JSON frames such as ~h~ filtered before this step)
TradingView frame splitter
  (reads length prefix from ~m~<length>~m~<payload> to extract each payload)
        │
        ▼
json.loads() on each payload
        │
        ▼
yield dict
```

A single WebSocket frame may contain multiple concatenated TradingView messages (see [Message Framing](../architecture/websocket-protocol.md#message-framing)). The parser uses the length value in each `~m~<length>~m~` prefix to extract individual payloads — not simple delimiter splitting, which would break if a payload contained a literal `~m~`.

**Heartbeat echo**: if the client does not respond to `~h~` messages, TradingView drops the connection within seconds. `get_data_stream()` handles this internally — callers do not need to check for heartbeats.

**Message types in the stream**: the generator yields all message types. The `OHLCV` client filters for the ones it cares about:

| Message `m` field | Meaning |
|-------------------|---------|
| `du` | Bar data update (historical batch delivery) |
| `timescale_update` | Real-time bar update (live streaming) |
| `series_loading` | Server has started loading bars |
| `series_completed` | All requested bars delivered — `OHLCV` breaks the loop here |
| `symbol_error` | Symbol could not be resolved — `OHLCV` raises an exception |
| `qsd` | Quote state data — present when quote subscriptions are active |

**Termination**: the `OHLCV` client breaks out of the `get_data_stream()` loop when it receives `series_completed`. The generator itself runs indefinitely until the caller stops iterating or the connection closes.

## Error Handling

| Error | Source | Handling |
|-------|--------|----------|
| `ConnectionClosed` | WebSocket dropped | Propagates to caller; retry is the caller's responsibility |
| `WebSocketException` | Protocol error | Propagates to caller |
| `json.JSONDecodeError` | Malformed server message | Logged; the message is skipped |
| `RuntimeError` | `get_data_stream()` called before `connect()` | Raised immediately |

## Multiple Symbol Subscriptions

`add_multiple_symbols_to_sessions()` subscribes a list of symbols to the quote session only (no chart session). This is used by `get_latest_trade_info()`, which monitors trade-level updates across many symbols in a single connection without requesting OHLCV bars.

The first symbol in the list is used to configure the session (currency, session type, adjustment); all symbols are then added in one batch.

## See Also

- [Message Service](message-service.md) — message construction and framing
- [WebSocket Protocol](../architecture/websocket-protocol.md) — wire format and message flow
- [OHLCV Client](../api/chart/ohlcv.md) — the public interface that wraps this service
