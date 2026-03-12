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

Yes. Pass a `list[ScannerStock]` to `DataExporter`. See [Exporting Data](guides/exporting.md#scanner-results-export).

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

## Timezones

### Why are timestamps UTC?

All `OHLCVBar.timestamp` values are UTC Unix epoch floats — the number of seconds since
`1970-01-01T00:00:00Z`. This is the UTC invariant tvkit enforces: timestamps in the data layer are
always UTC, and timezone conversion is explicit and opt-in at the display boundary.

The reasons are practical:

- **No DST ambiguity** — UTC has no daylight saving time transitions, so arithmetic over epoch values is always unambiguous
- **No locale dependence** — a UTC epoch behaves identically on a server in New York, Bangkok, or anywhere else
- **Wire protocol compatibility** — TradingView sends timestamps as UTC Unix epoch values; tvkit preserves them exactly as received
- **Cross-dataset joins** — UTC is the natural common key when joining data from multiple exchanges in different time zones

To convert, use `tvkit.time`:

```python
from tvkit.time import convert_to_exchange_timezone

df_local = convert_to_exchange_timezone(df, "NASDAQ")  # America/New_York
```

See [Concepts: Timezones](concepts/timezones.md).

### Why is BINANCE timezone UTC?

Crypto exchanges such as `BINANCE`, `COINBASE`, and `KRAKEN` are mapped to `"UTC"` in the tvkit
exchange registry. This is intentional. Crypto markets:

- Trade **24/7** with no market open/close session
- Operate globally, not from a single physical location
- Express all data in UTC by convention

There is no "exchange-local time" for a crypto exchange the way there is for NYSE (`America/New_York`) or SET (`Asia/Bangkok`). UTC is the correct and meaningful timezone for crypto data.

```python
from tvkit.time import exchange_timezone

exchange_timezone("BINANCE")  # "UTC"
exchange_timezone("NASDAQ")   # "America/New_York"
exchange_timezone("SET")      # "Asia/Bangkok"
```

### How do I display timestamps in my local timezone?

Use `convert_to_timezone()` for any IANA timezone, or `convert_to_exchange_timezone()` to resolve
the timezone from an exchange code:

```python
from tvkit.time import convert_to_timezone, convert_to_exchange_timezone

# Any IANA timezone
df_local = convert_to_timezone(df, "Asia/Bangkok")

# Exchange code → IANA timezone automatically
df_ny = convert_to_exchange_timezone(df, "NASDAQ")     # America/New_York
df_bkk = convert_to_exchange_timezone(df, "SET")       # Asia/Bangkok
```

Both functions return a new DataFrame; the original is not mutated.

See [tvkit.time Reference](reference/time/index.md) and [Historical Data — Working with Timezones](guides/historical-data.md#working-with-timezones).

### Why are timestamps `float` instead of `datetime`?

Unix epoch floats are:

- **Compact** — a single float per bar vs. a full datetime object
- **Language-neutral** — trivially portable to JavaScript, SQL, or any other system
- **Wire-protocol compatible** — TradingView sends epoch values directly; storing them as-is avoids any round-trip conversion
- **Arithmetic-friendly** — computing durations is a simple subtraction; no timezone-aware subtraction required

Convert to `datetime` only when needed, at the display or analysis layer.

### Can I store timestamps as pandas datetime?

Yes. After converting with `convert_to_timezone()` or `convert_to_exchange_timezone()`, the
Polars `timestamp` column is a tz-aware `datetime[us, <tz>]`. You can convert to pandas via
`df.to_pandas()` if your downstream pipeline requires it.

The key principle is: keep timestamps as UTC epoch floats in the data layer, and convert to
`datetime` (Polars or pandas) only at the analysis or export layer. This prevents accidental local
time storage and keeps your pipeline timezone-agnostic.

---

## Errors and Troubleshooting

### I'm getting a `ConnectionClosed` error. What do I do?

The WebSocket connection was dropped by the server. This can happen due to network instability, rate limiting, or the server closing idle connections. Implement retry logic with exponential backoff. See [Real-Time Streaming — Error Handling](guides/realtime-streaming.md#error-handling-and-retry).

### tvkit raises `symbol_error`. What does that mean?

The server could not resolve the symbol. Check that the symbol format is correct (`EXCHANGE:SYMBOL`) and that the symbol is active on TradingView.

### Where do I report bugs?

Open an issue at [github.com/lumduan/tvkit/issues](https://github.com/lumduan/tvkit/issues). Include the tvkit version, Python version, and a minimal reproducible example.
