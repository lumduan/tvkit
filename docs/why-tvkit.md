# Why tvkit?

tvkit is a Python library for accessing TradingView's financial data APIs. This page explains the design decisions behind it and when it is the right tool.

## The Problem It Solves

TradingView provides a rich dataset — real-time OHLCV bars, a stock scanner with 100+ financial metrics, and macro indicators — but its WebSocket protocol is undocumented, session-based, and requires specific message sequencing. Connecting directly means:

- Implementing a custom WebSocket framing protocol (`~m~<len>~m~<json>`)
- Managing quote and chart session identifiers
- Handling heartbeats and reconnection logic
- Parsing TradingView-specific data structures

tvkit handles all of this, exposing a clean async interface.

## Why Async-First?

Financial data workloads are I/O-bound: you spend most of your time waiting for network responses. Python's `asyncio` allows concurrent I/O without threads, which means:

- Multiple symbols can be fetched concurrently with `asyncio.gather()`
- A streaming subscription does not block the event loop
- WebSocket connections are managed efficiently without thread-per-connection overhead

All tvkit I/O uses `websockets` (WebSocket) and `httpx` (HTTP) — both async-native libraries. Synchronous libraries such as `requests` or `websocket-client` are intentionally not used.

## Why TradingView Data?

TradingView aggregates data from hundreds of exchanges and data providers into a single, consistent API surface:

- **Global coverage**: 69 markets across North America, Europe, Asia Pacific, Middle East, and Latin America
- **Financial metrics**: 100+ scanner columns covering price, fundamentals, technicals, valuation, and cash flow
- **Macro indicators**: `INDEX:NDFI`, `USI:PCC`, and other breadth/sentiment indicators not available from most market data APIs
- **Consistent bar format**: OHLCV bars from equities, crypto, forex, and commodities all share the same data structure

## tvkit vs Rolling Your Own WebSocket Client

| Concern | Raw WebSocket | tvkit |
|---------|--------------|-------|
| Protocol framing | Manual — `~m~<len>~m~<json>` | Handled |
| Session management | Manual — quote + chart sessions | Handled |
| Heartbeat handling | Manual | Handled |
| Reconnection logic | Manual | Handled |
| Interval validation | Manual | Built-in `validate_interval()` |
| Symbol format conversion | Manual | Built-in `convert_symbol_format()` |
| Data models | Raw dicts | Pydantic-validated `OHLCV` objects |
| Export | Manual | `DataExporter` — CSV, JSON, Polars |

## Design Goals

1. **Minimal surface for the user** — one context manager, one `await`, one result.
2. **Type safety everywhere** — all data models use Pydantic; all functions have full type annotations; `mypy` strict mode passes.
3. **No hidden state** — connections are opened and closed inside context managers; no global connection pool.
4. **Fail loudly and early** — invalid intervals and symbols raise `ValueError` before any network call is made.
5. **No sync I/O** — every external call is async; blocking the event loop is never acceptable.

## Performance and Scale

tvkit is designed for production workloads. Latency figures are approximate, measured on a typical broadband connection; actual performance varies by region and network conditions.

| Operation | Typical Latency |
|-----------|----------------|
| Historical data fetch | 100–500ms per symbol |
| Market scanner query | 200–800ms per market |
| Real-time bar delivery | <50ms after bar close |
| Polars DataFrame export | 10–50ms for 1,000 bars |

Concurrent fetches scale linearly with `asyncio.gather()`.

## When Not to Use tvkit

tvkit may not be the right tool if:

- You require **officially licensed** exchange market data feeds (tvkit uses TradingView's consumer-facing data, not exchange-licensed feeds).
- You need **tick-level or millisecond-precision** data — tvkit delivers bars at the interval boundary, not individual trades.
- Your environment **cannot run asyncio-based applications** (e.g., some legacy synchronous frameworks).
- You need data covered by **financial regulations** that require a certified data vendor.

## See Also

- [Limitations](limitations.md) — known constraints and unsupported data types
- [Data Sources](data-sources.md) — what TradingView provides and its coverage gaps
- [Architecture](architecture/system-overview.md) — how the four tvkit modules fit together
