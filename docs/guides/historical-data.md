# Historical Data Guide

[Home](../index.md) > Guides > Historical Data

`get_historical_ohlcv()` fetches a fixed set of past OHLCV bars for any symbol and interval supported by TradingView. It opens a WebSocket connection, retrieves the bars, and closes the connection — returning a `list[OHLCVBar]`.

## Prerequisites

- tvkit installed: see [Installation](../getting-started/installation.md)
- Understand symbol format: see [Symbols](../concepts/symbols.md)
- Understand interval strings: see [Intervals](../concepts/intervals.md)

---

## Mode 1: Bar Count

Request the most recent N bars for a symbol.

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def fetch_recent_bars() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(
            exchange_symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=30,
        )

    for bar in bars:
        print(f"{bar.timestamp}  open={bar.open}  close={bar.close}  volume={bar.volume}")

asyncio.run(fetch_recent_bars())
```

`bars_count` accepts any positive integer up to `MAX_BARS_REQUEST`. Bars are returned oldest-first.

---

## Mode 2: Date Range

Request bars between two explicit dates using `start` and `end` parameters.

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def fetch_date_range() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(
            exchange_symbol="NASDAQ:AAPL",
            interval="1D",
            start="2024-01-01",
            end="2024-06-30",
        )

    print(f"Fetched {len(bars)} bars from 2024-01-01 to 2024-06-30")

asyncio.run(fetch_date_range())
```

`start` and `end` accept ISO 8601 date strings (`"YYYY-MM-DD"`) or Unix timestamps (integers). Times default to midnight UTC.

When both `bars_count` and `start`/`end` are provided, date range takes priority.

---

## Large Date Range Fetching (Automatic Segmentation)

For date ranges that span more bars than `MAX_BARS_REQUEST` (5,000), `get_historical_ohlcv()` automatically splits the request into segments and fetches them sequentially. Results are merged, deduplicated by timestamp, and sorted chronologically before being returned. No changes to your call site are required.

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.chart.exceptions import RangeTooLargeError

async def fetch_full_year_1min() -> None:
    async with OHLCV() as client:
        try:
            bars = await client.get_historical_ohlcv(
                exchange_symbol="BINANCE:BTCUSDT",
                interval="1",
                start="2024-01-01",
                end="2024-12-31",
            )
        except RangeTooLargeError as exc:
            print(f"Range too large: {exc}")
            return

    # tvkit automatically segments the request internally.
    # Note: actual accessible history depends on TradingView account tier.
    print(f"Fetched {len(bars)} 1-minute bars")

asyncio.run(fetch_full_year_1min())
```

**How segmentation works:**

1. tvkit estimates the bar count for the requested range
2. If the count exceeds `MAX_BARS_REQUEST`, the range is split into non-overlapping segments
3. Each segment is fetched with `_fetch_single_range()` (not a recursive call to the public method)
4. Segments covering periods with no data (weekends, holidays) are silently skipped
5. Results are merged, deduplicated, and returned as a single sorted list

**Limits:**

- Monthly and weekly intervals are never segmented — they always use a single request
- If the range would require more than `MAX_SEGMENTS` (2,000) segments, `RangeTooLargeError` is raised before any fetch begins. Narrow the date range or use a wider interval

---

## The `max_bars` Lookback Window

Automatic segmentation handles the per-request bar limit, but a separate server-side policy controls how many bars are accessible at all: the **`max_bars` window**.

> **Key concept:** TradingView serves at most `max_bars` bars counted **backward from the
> latest bar in the series** — not from wall-clock current time.

**Range mode is a filter, not a deeper lookup.** The server first retrieves the last
`max_bars` bars, then filters to your requested `start`/`end` range. If your date range
falls entirely before the oldest accessible bar, you get 0 bars with no error raised.

```text
         ◄──────── max_bars window ──────────►
         │                                   │
[oldest accessible bar]          [latest bar in series]
         │                                   │
         │   ← range filter works here →     │
         │
 dates here → 0 bars, no error
```

The same window applies to **segmented fetch**: segments beyond the window return empty
results silently. The caller receives a valid but partial result.

**Accessible depth by interval and account tier** (assumes ~24 h/day continuous trading;
instruments with trading gaps span proportionally more calendar days):

| Interval   | Free / Basic | Essential / Plus | Premium   | Ultimate  |
| ---------- | ------------ | ---------------- | --------- | --------- |
| 1 minute   | ≈3.5 days    | ≈7 days          | ≈14 days  | ≈28 days  |
| 5 minutes  | ≈17 days     | ≈35 days         | ≈70 days  | ≈140 days |
| 15 minutes | ≈52 days     | ≈104 days        | ≈208 days | ≈416 days |
| 1 hour     | ≈7 months    | ≈14 months       | ≈28 months| ≈56 months|
| 1 day      | ≈13 years    | Unlimited        | Unlimited | Unlimited |

These figures are derived from `max_bars` counts. TradingView does not publish official
figures; limits may change.

**`MAX_BARS_REQUEST` vs `max_bars`:**

| Concept | What it controls |
| ------- | ---------------- |
| `MAX_BARS_REQUEST` | Protocol limit — max bars in a single WebSocket request |
| `max_bars` (lookback window) | Account policy — total bars accessible, counted from the latest bar |

See [Limitations — The `max_bars` Window](../limitations.md#tradingview-historical-depth-limitation--the-max_bars-window) for full details.

---

## Why did my request return fewer bars than expected?

If your result contains fewer bars than the date range would suggest, one of these reasons applies:

- **Outside the `max_bars` window** — your requested `start` date is before the oldest bar accessible for your account tier. The window is measured from the latest bar in the series, not from wall-clock time. Segments outside the window return 0 bars silently. Upgrade your account or shorten the date range.
- **Market gaps** — weekends, public holidays, and illiquid periods contain no bars. Segments covering these periods are skipped. This is expected behavior, not a bug.
- **Bar count mode** — `bars_count` mode always returns at most N bars counting backward from the latest bar in the series. Use `start`/`end` range mode to target a specific historical window within the `max_bars` limit.

See [Limitations → TradingView Historical Depth Limitation](../limitations.md) for account-tier depth figures.

---

## Converting Timestamps

Each `OHLCVBar` has a `timestamp` field expressed as a UTC Unix epoch float (seconds). Convert to ISO 8601 with the utility function:

```python
from tvkit.api.utils import convert_timestamp_to_iso

date_string = convert_timestamp_to_iso(bar.timestamp)
print(date_string)  # "2024-01-15T09:30:00+00:00"
```

---

## Working with Timezones

All `OHLCVBar.timestamp` values are **UTC epoch floats**. tvkit never stores local time internally. Use `tvkit.time` to convert for display or analysis.

### Full Workflow: Fetch → Convert → Display

The most common pattern — download bars, export to a DataFrame, then convert timestamps to the exchange's local timezone for plotting:

```python
import asyncio
import polars as pl
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter
from tvkit.time import convert_to_exchange_timezone

async def fetch_with_local_time(symbol: str, exchange: str) -> pl.DataFrame:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(symbol, "60", bars_count=10)

    exporter = DataExporter()
    df = await exporter.to_polars(bars)

    # Internal timestamps are UTC — convert for display
    print("UTC epoch:", df["timestamp"].head(3))

    df_local = convert_to_exchange_timezone(df, exchange)
    print("Local time:", df_local["timestamp"].head(3))
    return df_local

# NASDAQ → America/New_York
asyncio.run(fetch_with_local_time("NASDAQ:AAPL", "NASDAQ"))
# timestamp column changes from:
#   1705312200.0  (UTC epoch float)
# to:
#   2024-01-15 09:30:00 EST
```

The original DataFrame is never mutated — `convert_to_exchange_timezone` returns a new DataFrame.

### Convert to Any IANA Timezone

Use `convert_to_timezone()` to convert to any arbitrary timezone:

```python
from tvkit.time import convert_to_timezone

# Convert to Bangkok time for SET analysis
df_bkk = convert_to_timezone(df, "Asia/Bangkok")

# Convert to London time for LSE analysis
df_lon = convert_to_timezone(df, "Europe/London")
```

### Convert Using Exchange Code

Use `convert_to_exchange_timezone()` to let tvkit resolve the exchange code automatically:

```python
from tvkit.time import convert_to_exchange_timezone

df_ny  = convert_to_exchange_timezone(df, "NYSE")      # America/New_York
df_bkk = convert_to_exchange_timezone(df, "SET")       # Asia/Bangkok
df_utc = convert_to_exchange_timezone(df, "BINANCE")   # UTC (crypto, 24/7)
```

Crypto exchanges like `BINANCE` and `COINBASE` map to `"UTC"`. This is correct — they trade 24/7
with no market open/close session and no concept of exchange-local time.

### When to Keep UTC

Do **not** convert timestamps for backtesting, ML training, or cross-dataset joins. Converting
early introduces DST gaps and makes datasets from different exchanges harder to join. Convert at
the display or report layer only.

See [Concepts: Timezones](../concepts/timezones.md) for the full rationale, and
[tvkit.time Reference](../reference/time/index.md) for the complete API.

---

## Exporting to Polars DataFrame

Convert the bar list to a Polars DataFrame for analysis or export:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def export_to_polars() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=90)

    exporter = DataExporter()
    df = await exporter.to_polars(bars, add_analysis=True)
    print(df.head())

asyncio.run(export_to_polars())
```

`add_analysis=True` appends SMA, VWAP, and other technical columns automatically.

---

## Backtesting Pipeline Integration

A typical backtesting workflow:

```python
import asyncio
import polars as pl
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def build_backtest_dataset(symbol: str, interval: str, start: str, end: str) -> pl.DataFrame:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(
            exchange_symbol=symbol,
            interval=interval,
            start=start,
            end=end,
        )

    exporter = DataExporter()
    df = await exporter.to_polars(bars, add_analysis=True)

    # Save for reuse
    df.write_parquet(f"data/{symbol.replace(':', '_')}_{interval}.parquet")
    return df

asyncio.run(build_backtest_dataset("NASDAQ:AAPL", "1D", "2020-01-01", "2024-12-31"))
```

---

## See Also

- [Streaming vs Historical](../concepts/streaming-vs-historical.md) — when to use historical vs streaming
- [Real-time Streaming guide](realtime-streaming.md) — combining history with live data
- [Exporting Data guide](exporting.md) — CSV, JSON, and Parquet export
- [Intervals](../concepts/intervals.md) — valid interval strings
- [OHLCV reference](../reference/chart/ohlcv.md) — full method signature
- [Segmented Fetch internals](../internals/segmented-fetch.md) — algorithm and implementation details
- [Limitations](../limitations.md) — TradingView historical depth and other constraints
