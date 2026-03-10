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

## Retry Strategy

`ConnectionService` automatically reconnects when the WebSocket closes unexpectedly, using a configurable exponential backoff strategy.

### Connection State Machine

The service follows an explicit state machine. States are defined in `ConnectionState` (importable from `tvkit.api.chart.services.connection_service`):

```text
┌─────────────────────────────────┐
│                                 │
┌────▼────┐                  ┌─────┴──────┐
│  IDLE   │── connect() ────▶│ CONNECTING │
└─────────┘                  └─────┬──────┘
                                   │ success
                            ┌──────▼──────┐
                            │  STREAMING  │◀─────────┐
                            └──────┬──────┘          │
                                   │ unexpected       │
                                   │ close            │
                            ┌──────▼──────┐          │
                            │RECONNECTING │          │
                            └──────┬──────┘          │
                                   │ success ─────────┘
                                   │ exhausted
                            ┌──────▼──────┐
                            │   FAILED    │
                            └─────────────┘
```

| From | Event | To | Action |
| --- | --- | --- | --- |
| `IDLE` | `connect()` called | `CONNECTING` | Open WebSocket |
| `CONNECTING` | Connection success | `STREAMING` | Start reader task |
| `STREAMING` | Unexpected close (`1006`) | `RECONNECTING` | Start backoff loop |
| `STREAMING` | Clean close (`1000`) | `IDLE` | No retry |
| `STREAMING` | `close()` called | `IDLE` | Set `_closing`, skip retry |
| `RECONNECTING` | Attempt success | `STREAMING` | Invoke `on_reconnect`, resume stream |
| `RECONNECTING` | Attempts exhausted | `FAILED` | Raise `StreamConnectionError` |

### Backoff Formula

```text
delay = min(base_backoff × 2^(attempt - 1), max_backoff)
delay = min(delay + random(0, jitter_range), max_backoff)
```

Both clamp operations are required: the first caps exponential growth; the second ensures jitter cannot push the final delay past `max_backoff`.

| Parameter | Default | Description |
| --- | --- | --- |
| `max_attempts` | `5` | Total attempts before `StreamConnectionError` |
| `base_backoff` | `1.0` | Base delay in seconds |
| `max_backoff` | `30.0` | Maximum delay cap in seconds |
| `jitter_range` | `0.0` | Additive jitter range in seconds (0 = disabled) |

### Example Backoff Timeline (default config)

```text
t=0s    connection lost
t=1s    attempt 1 (delay 1s)  → failure
t=3s    attempt 2 (delay 2s)  → failure
t=7s    attempt 3 (delay 4s)  → failure
t=15s   attempt 4 (delay 8s)  → success → stream resumes
```

### Reconnect Trigger Timing

The `on_reconnect` callback is invoked **after** a successful reconnect and **before** the message processing loop resumes. In `_reconnect_with_backoff()`:

```python
await self._connect()                        # 1. new WebSocket established
self._state = ConnectionState.STREAMING
self._reader_task = create_task(...)        # 2. reader starts (writes to queue)
if self._on_reconnect:
    await self._on_reconnect()              # 3. caller restores subscription
return                                       # 4. get_data_stream() resumes
```

This ordering guarantees that subscription messages are sent before any data frames are consumed by the caller.

### Connection Reset on Each Attempt

Before each reconnect attempt, `_reset_connection()` tears down the previous connection:

1. Cancel and await the reader task (suppress `CancelledError`)
2. Close `self._ws` if not already closed (suppress all exceptions)
3. Reset both references to `None`
4. Drain the message queue to remove stale messages and leftover sentinels

This runs **before** the backoff sleep, ensuring stale tasks and WebSocket references are freed immediately rather than held open during the delay.

### Intentional Close vs Unexpected Close

A `_closing` flag prevents retry when the caller intentionally closes the connection:

```python
# Intentional — no retry
self._closing = True
await self._ws.close()

# Unexpected — retry triggered
except ConnectionClosed:
    if not self._closing:
        await self._reconnect_with_backoff()
```

### Single Reconnect Loop Guard

`_reconnect_with_backoff()` is protected by `_reconnect_lock` (an `asyncio.Lock` held for the entire retry loop). A second concurrent caller blocks at the lock boundary until the active loop completes (success or exhaustion). This prevents duplicate retry loops if both the reader task and a heartbeat monitor observe the same failure simultaneously.

### Session Restoration

`ConnectionService` does not know about symbols or subscriptions. The `on_reconnect` callback is provided by the caller (`OHLCV._restore_session`) and is responsible for re-establishing the application-level session after the transport reconnects. See [OHLCV Client](../reference/chart/ohlcv.md) for details.

## Error Handling

| Error | Source | Handling |
|-------|--------|----------|
| `ConnectionClosed` (unexpected) | WebSocket dropped | `_reconnect_with_backoff()` triggered |
| `ConnectionClosed` (clean, `1000`) | Server/client close | Stream ends normally, no retry |
| `StreamConnectionError` | All attempts exhausted | Raised from `get_data_stream()` |
| `WebSocketException` | Protocol error during reconnect | Attempt counted as failure, backoff continues |
| `json.JSONDecodeError` | Malformed server message | Logged; the message is skipped |
| `RuntimeError` | `get_data_stream()` called before `connect()` | Raised immediately |

## Multiple Symbol Subscriptions

`add_multiple_symbols_to_sessions()` subscribes a list of symbols to the quote session only (no chart session). This is used by `get_latest_trade_info()`, which monitors trade-level updates across many symbols in a single connection without requesting OHLCV bars.

The first symbol in the list is used to configure the session (currency, session type, adjustment); all symbols are then added in one batch.

## See Also

- [Message Service](message-service.md) — message construction and framing
- [WebSocket Protocol](../architecture/websocket-protocol.md) — wire format and message flow
- [OHLCV Client](../api/chart/ohlcv.md) — the public interface that wraps this service
