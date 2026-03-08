# Architecture Decisions

This page records the key design decisions made during tvkit's development, why each choice was made, and what the trade-offs are. It is intended for contributors who need to understand the rationale before making changes.

**Decisions covered**:

- Async-first I/O model
- Pydantic validation for all data models
- Separation between `ConnectionService` and `MessageService`
- Context-manager based client lifecycle
- Range mode requires two protocol messages
- Symbol format auto-conversion at the boundary
- Independent chart and scanner modules
- No global connection pool

---

## Async-First I/O

**Decision**: every external I/O operation uses `async/await`. Synchronous I/O is not used anywhere in the library.

**Why**: WebSocket streaming blocks indefinitely while waiting for server messages. In a synchronous model, this would block the entire thread. Async I/O allows the event loop to yield while waiting, so the caller can run other tasks concurrently (e.g., fetching multiple symbols with `asyncio.gather()`).

**Libraries chosen**: `websockets` for WebSocket, `httpx` for HTTP. Both are async-native. `requests` and `websocket-client` are explicitly excluded — using them would require thread-based concurrency and block the event loop.

**Trade-off**: tvkit is not usable from purely synchronous codebases without wrapping in `asyncio.run()`. This is accepted; the alternative would require maintaining both sync and async code paths.

---

## Pydantic for All Data Models

**Decision**: every data structure is a Pydantic `BaseModel` with full type annotations and field descriptions.

**Why**: TradingView's WebSocket protocol sends raw JSON with numeric arrays (`[timestamp, open, high, low, close, volume]`). Without validation, a malformed server response would silently produce incorrect data. Pydantic catches structural errors at the boundary and gives typed objects to callers.

**Trade-off**: Pydantic adds a small parsing overhead per bar. At thousands of bars per second this would matter; at the rates tvkit operates (hundreds of bars per request), it does not.

---

## ConnectionService and MessageService Are Separate

**Decision**: WebSocket management (`ConnectionService`) and message construction (`MessageService`) are two distinct classes.

**Why**: separation of concerns. `ConnectionService` owns the socket and the incoming message stream. `MessageService` owns the outgoing message format and session identifier generation. Neither needs to know about the other's implementation details.

**Coupling point**: `ConnectionService` accepts a `send_message_func: Callable[[str, list[Any]], Awaitable[None]]` parameter rather than a `MessageService` instance. This keeps the two services decoupled and makes `ConnectionService` independently testable by passing a mock callable.

---

## OHLCV Is a Context Manager

**Decision**: the primary public API is an `async with OHLCV() as client:` context manager, not a standalone class with manual lifecycle methods.

**Why**: WebSocket connections must be closed when done. A context manager enforces this — the connection always closes on `__aexit__`, even if an exception is raised. Manual lifecycle methods (`connect()` / `close()`) are error-prone and easy to forget.

**Trade-off**: callers cannot reuse a single `OHLCV` instance across multiple `async with` blocks. A new connection is opened for each context. This is acceptable because each `get_historical_ohlcv()` call is a short-lived operation. To fetch multiple symbols concurrently, open multiple contexts:

```python
async with asyncio.TaskGroup() as tg:
    task_a = tg.create_task(fetch("NASDAQ:AAPL"))
    task_b = tg.create_task(fetch("NASDAQ:MSFT"))
```

---

## Range Mode Requires Two Protocol Messages

**Decision**: date-range historical requests send `create_series` followed immediately by `modify_series`.

**Why**: the TradingView server requires `create_series` to initialize the series subscription before any range constraint can be applied. There is no single-message range request. `create_series` is sent with `bars_count = MAX_BARS_REQUEST` as a sentinel; `modify_series` then replaces the count-based request with the specified range. The two-message sequence is a protocol requirement, not a tvkit design choice.

```text
create_series  (bars_count = MAX_BARS_REQUEST, range = "")
      │
      ▼
modify_series  (range = "r,<from_unix>:<to_unix>")
      │
      ▼
data stream    (server returns only bars within the window)
```

**Implication**: `modify_series` must be sent before the data-receive loop starts. `ConnectionService.add_symbol_to_sessions()` handles this sequencing internally.

---

## Symbol Format Auto-Conversion

**Decision**: all public methods automatically convert `EXCHANGE-SYMBOL` (dash) to `EXCHANGE:SYMBOL` (colon) before use.

**Why**: some external data sources and user inputs use dash notation. TradingView's protocol requires colon notation. Rather than requiring callers to always use the correct format, tvkit converts at the boundary.

```text
Input:   USI-PCC   →   Output: USI:PCC
Input:   NASDAQ:AAPL → Output: NASDAQ:AAPL  (unchanged, already correct)
```

**Implementation**: `convert_symbol_format()` in `tvkit.api.utils` returns a `SymbolConversionResult` with both the original and converted symbol. All five public `OHLCV` methods call this before passing the symbol to protocol messages.

---

## Scanner and Chart Are Independent Modules

**Decision**: `tvkit.api.chart` and `tvkit.api.scanner` share no code beyond the utilities in `tvkit.api.utils`.

**Why**: the two APIs are fundamentally different — chart uses WebSocket streaming, scanner uses HTTPS POST. They have different models, different error conditions, and different use cases. Sharing code between them would create inappropriate coupling.

**Implication**: a user who only needs the scanner does not need to understand or import anything from the chart module, and vice versa.

---

## No Global Connection Pool

**Decision**: there is no shared connection pool or singleton. Each `OHLCV` context manager opens its own connection.

**Why**: global state creates hidden dependencies and makes concurrent use unpredictable. Each context manager is self-contained — it opens, uses, and closes its own connection. Multiple concurrent `OHLCV` contexts work correctly without coordination.

**Trade-off**: concurrent fetches for multiple symbols each open their own connection. For large-scale parallel fetches, this increases connection overhead. `get_latest_trade_info()` exists for the common case of monitoring many symbols over a single persistent connection.

## See Also

- [System Overview](../architecture/system-overview.md) — how the four modules fit together
- [Connection Service](../internals/connection-service.md) — implementation details behind several of these decisions
- [Testing Strategy](testing-strategy.md) — how the async-first and decoupled design affects tests
