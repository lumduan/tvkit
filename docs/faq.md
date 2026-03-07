# Frequently Asked Questions

## General

### Is tvkit an official TradingView product?

No. tvkit is an independent open-source library. It reverse-engineers TradingView's WebSocket and HTTP APIs. It is not affiliated with, endorsed by, or supported by TradingView Inc.

### Does tvkit require a TradingView account?

No. tvkit accesses the same public data endpoints that TradingView's browser application uses for unauthenticated visitors. No login, API key, or subscription is required.

### Is using tvkit allowed by TradingView?

tvkit accesses publicly available endpoints used by TradingView's web client. However, TradingView's terms of service may restrict automated data collection. Users are responsible for ensuring their usage complies with TradingView's policies.

### Can I use tvkit for automated trading?

tvkit is a data access library only. It does not provide order execution or brokerage integration. Use it to fetch and analyze market data, not to place trades.

### Is the data real-time?

It depends on the exchange. Major US equities (NYSE, NASDAQ) are typically delayed 15 minutes for non-subscribed users. Crypto and forex data are generally real-time. See [Data Sources](data-sources.md) for the full breakdown.

---

## Installation and Setup

### What Python version is required?

Python 3.11 or later. tvkit uses modern async features such as `asyncio.TaskGroup` and advanced typing features introduced in Python 3.11.

### How do I install tvkit?

```bash
pip install tvkit
# or with uv (recommended):
uv add tvkit
```

See [Installation](getting-started/installation.md) for full instructions including source installation.

### Why does my script hang at `asyncio.run()`?

You are likely calling `asyncio.run()` inside an already-running event loop (e.g., inside a Jupyter notebook or another async framework). In Jupyter and similar environments, call the async APIs directly with `await`:

```python
async with OHLCV() as client:
    bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", 100)
```

In other contexts, structure the entire program as an async function and call `asyncio.run()` once at the top level.

---

## Data Access

### What symbol format does tvkit use?

Symbols follow the `EXCHANGE:SYMBOL` format (e.g., `NASDAQ:AAPL`, `BINANCE:BTCUSDT`, `FOREX:EURUSD`). tvkit also accepts dash format (`USI-PCC`) and auto-converts it to the colon format. See [Symbols](concepts/symbols.md).

### How many bars can I fetch at once?

Up to 5,000 bars per request in count mode. For more data, use date-range mode with `start` and `end` parameters, or implement segmented fetches. See [Historical Data](guides/historical-data.md).

### How far back can historical data go?

It depends on the symbol and interval. Daily data for major equities often goes back decades, while intraday data (minutes, seconds) may be limited to months or a few years depending on the exchange and TradingView's data retention.

### Are there rate limits?

TradingView does not publish official rate limits for its WebSocket or scanner APIs. Excessive request rates may cause the server to close connections. tvkit does not enforce client-side rate limiting, so implement reasonable pacing for high-frequency scripts.

### Can I stream multiple symbols at the same time?

For real-time quote monitoring across many symbols, use `get_latest_trade_info()` — it subscribes multiple symbols over a single connection. For independent OHLCV streams, open separate `OHLCV` contexts concurrently with `asyncio.gather()` or a `TaskGroup`.

### Why is my symbol returning no data?

Common causes:

- **Wrong format**: use `EXCHANGE:SYMBOL`, not just the ticker. Try `NASDAQ:AAPL`, not `AAPL`.
- **Delisted or invalid symbol**: verify the symbol exists on TradingView's website.
- **Unsupported market**: check [Data Sources](data-sources.md) for supported markets.
- **Interval mismatch**: some symbols only have daily data. Try `"1D"` if a shorter interval returns nothing.

### What intervals are supported?

tvkit supports all TradingView intervals: seconds (`1S`, `5S`), minutes (`1`, `5`, `15`, `30`, `45`), hours expressed as minutes (`60` = 1 h, `120` = 2 h, `240` = 4 h), and daily/weekly/monthly (`1D`, `1W`, `1M`). See [Intervals](concepts/intervals.md).

---

## Scanner

### How many markets does the scanner support?

69 global markets across 6 regions. See [Data Sources](data-sources.md) for the full list.

### Can I filter scanner results by multiple criteria?

Yes. Pass a list of filter objects to the `filters` parameter. All filters are combined with AND logic. See [Scanner Guide](guides/scanner.md).

### What columns are available in scanner results?

101+ columns covering price, fundamentals, technical indicators, valuation, and more. They are organized into named column sets (`BASIC`, `FUNDAMENTALS`, `TECHNICAL_INDICATORS`, etc.) that can be combined. See [Scanner Column Sets](concepts/scanner-columns.md).

---

## Export

### What export formats does tvkit support?

Polars DataFrames, CSV files, and JSON files. Parquet export is possible via Polars directly after receiving a DataFrame. See [Exporting Data](guides/exporting.md).

### Can I export scanner results?

Yes. Pass a `list[ScannerStock]` to `DataExporter`. See [Exporting Data](guides/exporting.md#exporting-scanner-results).

---

## Advanced Usage

### Can I reuse an OHLCV connection across multiple requests?

No. Each `async with OHLCV() as client:` block opens and closes its own WebSocket connection. For concurrent fetches, create multiple contexts:

```python
async def fetch(symbol: str) -> list[OHLCVBar]:
    async with OHLCV() as client:
        return await client.get_historical_ohlcv(symbol, "1D", 100)

results = await asyncio.gather(fetch("NASDAQ:AAPL"), fetch("NASDAQ:MSFT"))
```

---

## Errors and Troubleshooting

### I'm getting a `ConnectionClosed` error. What do I do?

The WebSocket connection was dropped by the server. This can happen due to network instability, rate limiting, or the server closing idle connections. Implement retry logic with exponential backoff. See [Real-Time Streaming — Error Handling](guides/realtime-streaming.md#error-handling).

### tvkit raises `symbol_error`. What does that mean?

The server could not resolve the symbol. Check that the symbol format is correct (`EXCHANGE:SYMBOL`) and that the symbol is active on TradingView.

### Where do I report bugs?

Open an issue at [github.com/lumduan/tvkit/issues](https://github.com/lumduan/tvkit/issues). Include the tvkit version, Python version, and a minimal reproducible example.
