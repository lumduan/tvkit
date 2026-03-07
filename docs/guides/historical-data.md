# Historical Data Guide

`get_historical_ohlcv()` fetches a fixed set of past OHLCV bars for any symbol and interval supported by TradingView. It opens a WebSocket connection, retrieves the bars, and closes the connection — returning a `list[OHLCV]`.

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

## Bar Count Limit: MAX_BARS_REQUEST

TradingView caps the number of bars returned per request. This limit is exposed as `MAX_BARS_REQUEST`:

```python
from tvkit.api.chart.utils import MAX_BARS_REQUEST

print(MAX_BARS_REQUEST)  # e.g. 5000
```

If you need more bars than this limit, fetch in segments using date-range mode:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def fetch_full_year() -> list:
    all_bars: list = []
    segments = [
        ("2023-01-01", "2023-06-30"),
        ("2023-07-01", "2023-12-31"),
    ]
    async with OHLCV() as client:
        for start, end in segments:
            bars = await client.get_historical_ohlcv(
                exchange_symbol="BINANCE:BTCUSDT",
                interval="60",
                start=start,
                end=end,
            )
            all_bars.extend(bars)
    return all_bars
```

---

## Converting Timestamps

Each `OHLCV` bar has a `timestamp` field expressed as a Unix timestamp (seconds). Convert to ISO 8601 with the utility function:

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
