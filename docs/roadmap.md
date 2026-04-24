# Roadmap

This page outlines what is planned, currently in progress, and under discussion for tvkit. It is a living document — priorities may evolve based on community feedback.

tvkit is evolving toward a **high-performance data infrastructure library for TradingView data**, focusing on reliability, scalability, and reproducible datasets for research and automation.

---

## Recently Shipped

- **v0.11.0** — Dividend-Adjusted OHLCV (`Adjustment` enum with `SPLITS` / `DIVIDENDS`; `adjustment` keyword parameter on `get_historical_ohlcv()`; `backadjustment: "default"` added to historical OHLCV WebSocket payload — protocol correctness fix)
- **v0.10.0** — Async Batch Downloader (`tvkit.batch`: `batch_download()`, bounded concurrency via semaphore, per-symbol retry with exponential backoff, `BatchDownloadSummary`, partial failure model, opt-in pre-flight symbol validation)
- **v0.9.0** — Data Integrity Validation (`tvkit.validation`: duplicate/monotonic/OHLC/volume/gap checks; `DataExporter` integration with `validate`, `strict`, `interval` parameters)
- **v0.8.0** —  Symbol Normalization 
- **v0.7.0** — Authentication
- **v0.6.0** — Timezone Handling
- **v0.5.0** — Segmented Historical Fetch
- **v0.4.0** — Connection retry with exponential backoff for `OHLCV` WebSocket client
- **Documentation refactor**
- **v0.3.0** — Historical OHLCV date-range mode (`start`/`end` parameters for `get_historical_ohlcv()`)
- **v0.1.5** — Symbol format auto-conversion (dash → colon notation)
- **v0.1.4** — Multi-market scanner with 69 markets and 101+ columns
- **v0.1.0** — Initial release: real-time OHLCV streaming and historical data

---

## Planned

These are confirmed improvements that will transform tvkit from a simple data client into a **robust, reliable data infrastructure layer**.

### Core Data Infrastructure

These features establish deterministic, consistent data handling across the entire library.

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

#### Async Scanner Pagination

Automatic pagination for scanner queries that exceed the server's per-request limit.

---

#### Type Stubs and IDE Completion

Improved inline type annotations and `py.typed` marker validation to ensure tvkit is fully recognized by pyright and mypy in strict mode.

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

- **Real-time order book data** — Level 2 (order book) data is not available via the public WebSocket protocol

---

## Contributing

If you'd like to contribute to any roadmap item, please open an issue on GitHub first to discuss the approach and avoid duplication of effort. See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed contribution guidelines.
