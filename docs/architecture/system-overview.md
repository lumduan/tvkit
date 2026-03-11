# System Overview

tvkit is structured as four independent modules that can be used separately or composed together.

## Module Map

```text
tvkit/
├── tvkit.api.chart          # Real-time WebSocket streaming
├── tvkit.api.scanner        # HTTP-based market scanner
├── tvkit.api.utils          # Shared utilities (symbols, timestamps, indicators)
└── tvkit.export             # Multi-format data export
```

## Component Diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│                        Your Application                          │
└───────────┬──────────────┬──────────────┬────────────────────────┘
            │              │              │
            ▼              ▼              ▼
   ┌────────────────┐ ┌──────────────┐ ┌───────────────┐
   │  tvkit.api.    │ │ tvkit.api.   │ │ tvkit.export  │
   │  chart         │ │ scanner      │ │               │
   │  ──────────    │ │ ──────────── │ │ ─────────────  │
   │  OHLCV client  │ │ ScannerSvc   │ │ DataExporter  │
   │  ConnectionSvc │ │ 69 markets   │ │ PolarsFormatter│
   │  MessageSvc    │ │ 100+ cols    │ │ JSONFormatter │
   │  SegmentedFetch│ │              │ │ CSVFormatter  │
   └───────┬────────┘ └──────┬───────┘ └───────┬───────┘
           │                 │                 │
           │ WebSocket       │ HTTPS           │
           ▼                 ▼                 │
   ┌──────────────────────────────────┐        │
   │       TradingView APIs           │        │
   │  wss://data.tradingview.com/...  │        │
   │  https://scanner.tradingview.com │        │
   └──────────────────────────────────┘        │
                                               ▼
                                    ┌────────────────────┐
                                    │  Polars / JSON / CSV│
                                    └────────────────────┘
```

## Module Descriptions

### `tvkit.api.chart` — Real-time WebSocket Streaming

**Purpose**: Stream live OHLCV bars and retrieve historical bars for any TradingView symbol.

**Key class**: `OHLCV` — the primary async context manager for all chart operations.

**Internal services**:
- `ConnectionService` — manages WebSocket lifecycle, session init, symbol subscription
- `MessageService` — constructs and sends TradingView protocol messages
- `SegmentedFetchService` — splits large date ranges into segments, fetches sequentially, merges/deduplicates results (v0.5.0+)

**Methods exposed**:
- `get_historical_ohlcv()` — fetch N bars or a date range; returns `list[OHLCV]`
- `get_ohlcv()` — stream live bars; returns `AsyncGenerator[OHLCV, None]`
- `get_quote_data()` — stream quote updates for a symbol
- `get_latest_trade_info()` — monitor multiple symbols in one connection
- `get_ohlcv_raw()` — access raw parsed messages for advanced use

**Protocol**: TradingView custom WebSocket — see [WebSocket Protocol](websocket-protocol.md).

---

### `tvkit.api.scanner` — Multi-Market Scanner

**Purpose**: Screen stocks across 69 global markets using 100+ financial metrics via HTTP.

**Key class**: `ScannerService` — async HTTP client with retry logic.

**Key components**:
- `markets.py` — `Market` enum (69 markets), `MarketRegion` enum (5 regions), region grouping helpers
- `models/scanner.py` — `ScannerRequest`, `ScannerFilter`, `ColumnSets`, `ScannerStock`

**Methods exposed**:
- `scan_market(market, request)` — scan a single market; returns `ScannerResponse`

**Helper functions**:
- `create_comprehensive_request()` — request builder with defaults
- `get_markets_by_region()` — filter markets by region

**Protocol**: HTTPS POST to `https://scanner.tradingview.com/`.

---

### `tvkit.api.utils` — Shared Utilities

**Purpose**: Cross-cutting utilities used by both chart and scanner modules.

**Key utilities**:
- `convert_timestamp_to_iso()` — Unix timestamp → ISO 8601 string
- `validate_symbols()` — async symbol existence check via TradingView HTTP
- `convert_symbol_format()` — dash-to-colon symbol conversion; returns `SymbolConversionResult`
- Indicator search and metadata (`IndicatorData`, `StudyPayload`)

---

### `tvkit.export` — Data Export

**Purpose**: Convert tvkit data into multiple formats for analysis or persistence.

**Key class**: `DataExporter` — unified export interface.

**Formatters**:
- `PolarsFormatter` — converts to `polars.DataFrame` with optional technical analysis
- `JSONFormatter` — writes JSON files with optional metadata
- `CSVFormatter` — writes CSV files with optional metadata

**Export methods**:
- `to_polars(data, add_analysis)` — in-memory DataFrame
- `to_json(data, path, include_metadata)` — file export
- `to_csv(data, path, include_metadata)` — file export

---

## Key Dependencies

| Dependency | Role |
|------------|------|
| `websockets` | Async WebSocket client — all chart streaming |
| `httpx` | Async HTTP client — scanner API and symbol validation |
| `pydantic` | Data validation — all models across all modules |
| `polars` | DataFrame processing — export and analysis |
| `asyncio` | Event loop — all concurrent I/O |

## Async-First Rationale

Every I/O operation in tvkit is async. This is not a style preference — it is a correctness requirement:

- WebSocket streaming blocks indefinitely while awaiting bars; async prevents this from stalling the application.
- Scanner queries can be issued concurrently across markets with `asyncio.gather()`.
- Symbol validation uses async HTTP to avoid blocking.

Mixing sync I/O into this pipeline would require threads, which adds latency and complexity. All tvkit I/O uses async-native libraries (`websockets`, `httpx`) to avoid this.

## See Also

- [WebSocket Protocol](websocket-protocol.md) — TradingView message format and session flow
- [Connection Service internals](../internals/connection-service.md)
- [Message Service internals](../internals/message-service.md)
