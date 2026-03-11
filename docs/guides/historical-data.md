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

## TradingView Historical Depth Limitation

Automatic segmentation handles the per-request bar limit, but a separate server-side constraint controls how far back in time TradingView data is accessible: the **historical depth window**.

TradingView exposes approximately ≈5,000 bars backward from the current time for free/basic accounts. Paid tiers provide deeper access. The table below shows approximate accessible depth by interval and account tier:

| Interval | Free / Basic | Essential / Plus | Premium | Expert | Ultimate |
| -------- | ------------ | ---------------- | ------- | ------ | -------- |
| 1 minute | ≈3.5 days | ≈17 days | ≈1 month | ≈3 months | ≈6 months |
| 5 minutes | ≈17 days | ≈3 months | ≈6 months | ≈1 year | ≈2 years |
| 15 minutes | ≈52 days | ≈9 months | ≈1.5 years | ≈3 years | ≈6 years |
| 1 hour | ≈7 months | ≈3 years | ≈6 years | ≈12 years | ≈24 years |
| 1 day | ≈27 years | Unlimited | Unlimited | Unlimited | Unlimited |

These are approximate, empirical values. TradingView does not publish official figures and limits may change.

**What happens when a segment falls outside the accessible window:**

If a segment's date range is before the accessible window for your account tier, TradingView returns no bars for that segment. tvkit treats this as an empty result — it does not raise an error. This behavior mirrors TradingView's native chart behavior.

**This limit is distinct from `MAX_BARS_REQUEST`:**

| Concept | What it controls |
| ------- | ---------------- |
| `MAX_BARS_REQUEST` | Protocol limit on bars per single fetch request |
| Historical depth | Server-side rolling window of accessible history per account tier |

See [Limitations](../limitations.md) for the full depth table and further details.

---

## Why did my request return fewer bars than expected?

If your result contains fewer bars than the date range would suggest, one of these reasons applies:

- **Historical depth window** — your requested `start` date is before the accessible history for your TradingView account tier. Segments outside the window return empty results. Upgrade your account or shorten the date range.
- **Market gaps** — weekends, public holidays, and illiquid periods contain no bars. Segments covering these periods are skipped. This is expected behavior, not a bug.
- **Bar count mode** — `bars_count` mode always returns at most N bars counting backward from the present. Use `start`/`end` range mode to target a specific historical window.

See [Limitations → TradingView Historical Depth Limitation](../limitations.md) for account-tier depth figures.

---

## Converting Timestamps

Each `OHLCVBar` has a `timestamp` field expressed as a Unix timestamp (seconds). Convert to ISO 8601 with the utility function:

```python
from tvkit.api.utils import convert_timestamp_to_iso

date_string = convert_timestamp_to_iso(bar.timestamp)
print(date_string)  # "2024-01-15T09:30:00+00:00"
```

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
