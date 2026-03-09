# Roadmap

This page outlines what is planned, currently in progress, and under discussion for tvkit. It is a living document — priorities may evolve based on community feedback.

tvkit is evolving toward a **high-performance data infrastructure library for TradingView data**, focusing on reliability, scalability, and reproducible datasets for research and automation.

---

## Recently Shipped

- **v0.3.0** — Historical OHLCV date-range mode (`start`/`end` parameters for `get_historical_ohlcv()`)
- **v0.1.5** — Symbol format auto-conversion (dash → colon notation)
- **v0.1.4** — Multi-market scanner with 69 markets and 101+ columns
- **v0.1.0** — Initial release: real-time OHLCV streaming and historical data

---

## Planned

These are confirmed improvements that will transform tvkit from a simple data client into a **robust, reliable data infrastructure layer**.

### Core Data Infrastructure

These features establish deterministic, consistent data handling across the entire library.

#### Symbol Normalization Layer

Canonical symbol formatting across tvkit.

TradingView instruments can appear in multiple forms:

- `AAPL`
- `NASDAQ:AAPL`
- `BTCUSDT`
- `BINANCE:BTCUSDT`
- `btc/usdt`

The normalization layer ensures every symbol is represented consistently across cache keys, storage paths, batch downloads, and validation systems.

Proposed module: `tvkit.symbols`

```python
normalize_symbol("aapl")      # → "NASDAQ:AAPL"
normalize_symbol("btc/usdt")  # → "BINANCE:BTCUSDT"
```

---

#### Timezone Handling

Consistent timezone management for OHLCV data.

tvkit will operate **entirely in UTC internally**, while providing utilities to convert data into exchange local time, user-defined timezones, and research-specific timeframes.

Proposed module: `tvkit.time`

```python
convert_to_timezone(df, "Asia/Bangkok")
```

---

#### Data Integrity Validation

Validation utilities to guarantee OHLCV data consistency before caching, exporting, or analysis.

Checks may include:

- Monotonic timestamps
- Duplicate bars
- OHLC consistency (`low ≤ open ≤ close ≤ high`)
- Non-negative volume
- Gap detection

Proposed module: `tvkit.validation`

```python
validate_ohlcv(df)
```

---

#### Data Caching Layer

A multi-layered caching system to reduce redundant network requests and help circumvent TradingView rate limits.

Possible cache types:

- In-memory LRU cache
- Disk-based cache
- TTL-based expiration
- Partial range caching

```python
client = OHLCV(cache=True)
```

---

### Storage & Scalability

Features enabling large-scale historical data storage and high-throughput ingestion.

#### Parquet Data Lake Export

Partitioned Parquet export optimized for large datasets and machine learning pipelines.

```text
data/
  symbol=NASDAQ:AAPL/
    interval=1D/
      year=2024/
        part-000.parquet
```

Benefits:

- Fast columnar scans
- Incremental appending
- Efficient lazy loading
- Compatibility with data lake tooling

---

#### Async Batch Downloader

High-throughput historical downloader capable of fetching large symbol sets concurrently.

Features may include:

- Bounded concurrency
- Retry with exponential backoff
- Cache integration
- Partial progress recovery

```python
await batch_download(
    symbols=[...],
    interval="1D",
    bars_count=500,
    concurrency=5,
)
```

---

### Data Engineering Utilities

Tools designed to support research workflows and dataset construction.

#### OHLCV Resampling Utilities

Utilities for aggregating lower-timeframe bars into higher intervals.

```python
resample_ohlcv(df, "1D")
resample_ohlcv(df, "4H")
```

Aggregation rules: `open = first`, `high = max`, `low = min`, `close = last`, `volume = sum`.

Resampling will be timezone-aware and designed to preserve OHLCV integrity.

---

#### Feature Metadata Schema

A schema system describing dataset fields and derived indicators.

```json
{
  "close": {
    "type": "price",
    "source": "tradingview",
    "timezone": "UTC"
  },
  "sma_20": {
    "type": "indicator",
    "window": 20
  }
}
```

Potential use cases: dataset versioning, machine learning reproducibility, feature lineage, and auditability.

Proposed module: `tvkit.schema`

---

### API & Developer Experience

Enhancements focused on usability and developer ergonomics.

#### Segmented Historical Fetch

A built-in utility to automatically paginate through large date ranges by splitting them into multiple requests, eliminating the need for callers to implement pagination manually.

---

#### Connection Retry with Backoff

Built-in reconnection logic in `OHLCV` with configurable exponential backoff to prevent users from having to manually reopen connections after brief network drops.

---

#### Async Scanner Pagination

Automatic pagination for scanner queries that exceed the server's per-request limit.

---

#### Type Stubs and IDE Completion

Improved inline type annotations and `py.typed` marker validation to ensure tvkit is fully recognized by pyright and mypy in strict mode.

---

#### Documentation Refactor

Restructuring documentation into a layered hierarchy (concepts, guides, reference, architecture, internals) to improve navigability and long-term maintainability.

---

## Under Consideration

These ideas have been explored but are not yet committed:

- **WebSocket multiplexing** — sharing a single connection across multiple concurrent OHLCV subscriptions
- **CLI tool** — a command-line interface for executing fast historical data fetches without writing Python scripts
- **Pandas output** — optional DataFrame output alongside existing Polars support
- **Additional export formats** — Parquet and Excel as first-class targets in `DataExporter`
- **Indicator calculations** — built-in SMA, EMA, RSI computation on returned bar data

---

## Not Planned

The following are explicitly outside the scope of tvkit:

- **Order placement** — tvkit is a data library, not a trading execution platform
- **TradingView account authentication** — accessing premium data requires a TradingView subscription; tvkit focuses only on public endpoints
- **Real-time order book data** — Level 2 (order book) data is not available via the public WebSocket protocol

---

## Contributing

If you'd like to contribute to any roadmap item, please open an issue on GitHub first to discuss the approach and avoid duplication of effort. See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed contribution guidelines.
