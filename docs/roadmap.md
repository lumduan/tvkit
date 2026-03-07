# Roadmap

This page describes what is planned, in progress, and under consideration for tvkit. It is a living document — priorities may shift based on community feedback.

## Recently Shipped

- **v0.3.0** — Historical OHLCV date-range mode (`start`/`end` parameters for `get_historical_ohlcv()`)
- **v0.1.5** — Symbol format auto-conversion (dash → colon notation)
- **v0.1.4** — Multi-market scanner with 69 markets and 101+ columns
- **v0.1.0** — Initial release: real-time OHLCV streaming and historical data

## In Progress

- **Documentation refactor** — Restructuring docs into a layered hierarchy (concepts, guides, reference, architecture, internals)

## Planned

These are confirmed future improvements, roughly in priority order:

### Segmented Historical Fetch

A built-in utility to automatically paginate through large date ranges by splitting them into multiple requests, without the caller needing to implement pagination manually.

### Connection Retry with Backoff

Built-in reconnection logic in `OHLCV` with configurable exponential backoff, so short network drops do not require the caller to reopen a context.

### Async Scanner Pagination

Automatic result pagination for scanner queries that exceed the server's per-request limit.

### Type Stubs and IDE Completion

Improved inline type annotations and `py.typed` marker validation to ensure tvkit is fully recognized by pyright and mypy in strict mode.

## Under Consideration

These are ideas that have been discussed but not yet committed:

- **WebSocket multiplexing** — sharing a single connection across multiple concurrent OHLCV subscriptions
- **CLI tool** — a command-line interface for quick historical data fetches without writing Python
- **Pandas output** — optional Pandas DataFrame output alongside the existing Polars support
- **Additional export formats** — Parquet and Excel as first-class export targets in `DataExporter`
- **Indicator calculations** — built-in SMA, EMA, RSI computation on returned bar data

## Not Planned

The following are explicitly out of scope for tvkit:

- **Order placement** — tvkit is a data library, not a trading platform
- **TradingView account authentication** — accessing premium data requires a TradingView subscription; tvkit targets public endpoints only
- **Real-time order book data** — Level 2 data is not exposed via the public WebSocket protocol

## Contributing

If you want to work on a roadmap item, open an issue on GitHub before starting to discuss approach and avoid duplicate effort. See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.
