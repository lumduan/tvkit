# Real-time Streaming Guide

[Home](../index.md) > Guides > Real-time Streaming

`get_ohlcv()` streams live OHLCV bars over a persistent WebSocket connection. Each bar is yielded as it closes on TradingView. The connection remains open until you break the loop or exit the context manager.

## Prerequisites

- tvkit installed: see [Installation](../getting-started/installation.md)
- Understand symbol format: see [Symbols](../concepts/symbols.md)
- Understand interval strings: see [Intervals](../concepts/intervals.md)
- Understand the streaming model: see [Streaming vs Historical](../concepts/streaming-vs-historical.md)

---

## Basic Stream

A new `OHLCV` object is yielded for each completed bar.

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def stream_bitcoin() -> None:
    async with OHLCV() as client:
        async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="1"):
            print(f"close={bar.close:.2f}  volume={bar.volume:,.0f}")

asyncio.run(stream_bitcoin())
```

The `async with OHLCV()` context manager opens the connection on entry and closes it cleanly on exit. Always use the context manager — do not instantiate `OHLCV()` without it.

---

## Bar Timing

`get_ohlcv()` yields a bar **after it closes** for the requested interval. No partial bars are emitted.

| Interval | Bar emitted at |
|----------|---------------|
| `"1"` | Every minute |
| `"5"` | Every 5 minutes |
| `"60"` | Every hour |
| `"1D"` | Once per trading day |

---

## Limiting the Number of Bars

Break out of the loop after receiving the desired number of bars:

```python
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.chart.models.ohlcv import OHLCV as OHLCVBar

async def stream_n_bars(symbol: str, interval: str, n: int) -> list[OHLCVBar]:
    bars: list[OHLCVBar] = []
    async with OHLCV() as client:
        async for bar in client.get_ohlcv(symbol, interval=interval):
            bars.append(bar)
            if len(bars) >= n:
                break
    return bars
```

---

## Multiple Symbol Monitoring

`get_latest_trade_info()` monitors multiple symbols within a single WebSocket connection and yields trade updates as they arrive:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def monitor_portfolio() -> None:
    symbols = [
        "BINANCE:BTCUSDT",
        "NASDAQ:AAPL",
        "FOREX:EURUSD",
        "OANDA:XAUUSD",
        "INDEX:NDFI",
        "USI:PCC",
    ]

    async with OHLCV() as client:
        async for trade_info in client.get_latest_trade_info(symbols):
            print(f"Update: {trade_info}")

asyncio.run(monitor_portfolio())
```

Use `get_latest_trade_info()` when you need real-time price ticks across a portfolio rather than full OHLCV bars.

---

## Connection Management

The `OHLCV` context manager handles connection lifecycle automatically:

```python
async with OHLCV() as client:
    # connection is open here
    async for bar in client.get_ohlcv("NASDAQ:AAPL", interval="1D"):
        process(bar)
# connection is closed here — even if an exception occurred
```

Do not share a single `OHLCV` instance across multiple concurrent tasks. Each task should open its own context to avoid race conditions and connection conflicts.

---

## Error Handling and Retry

Network errors raise exceptions that propagate from the `async for` loop. Wrap the loop in a retry mechanism with exponential backoff:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def stream_with_retry(symbol: str, interval: str, max_retries: int = 5) -> None:
    delay = 1.0
    for attempt in range(max_retries):
        try:
            async with OHLCV() as client:
                async for bar in client.get_ohlcv(symbol, interval=interval):
                    print(f"bar: {bar.close}")
            return  # clean exit
        except Exception as exc:  # network errors, connection resets, WebSocket closes
            print(f"Attempt {attempt + 1} failed: {exc}. Retrying in {delay:.0f}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)
    raise RuntimeError(f"Failed to stream {symbol} after {max_retries} attempts")

asyncio.run(stream_with_retry("BINANCE:BTCUSDT", "1"))
```

If bars are missed during a disconnect, backfill using `get_historical_ohlcv()` before resuming the stream.

---

## Combining with Historical Data

A common pattern seeds a dataset with historical bars before starting the live stream:

1. Fetch recent history with `get_historical_ohlcv()`
2. Start streaming new bars with `get_ohlcv()`
3. Append each new bar to the historical dataset

See [Streaming vs Historical](../concepts/streaming-vs-historical.md) for a complete example.

---

## Memory Considerations

Long-running streams accumulate bars in memory if they are stored indefinitely. Flush data periodically to disk or a database to prevent unbounded memory growth.

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.chart.models.ohlcv import OHLCV as OHLCVBar
from tvkit.export import DataExporter

async def stream_and_export(symbol: str, flush_every: int = 100) -> None:
    exporter = DataExporter()
    buffer: list[OHLCVBar] = []

    async with OHLCV() as client:
        async for bar in client.get_ohlcv(symbol, interval="1"):
            buffer.append(bar)
            if len(buffer) >= flush_every:
                await exporter.to_csv(buffer, f"./export/{symbol.replace(':', '_')}.csv")
                buffer.clear()

asyncio.run(stream_and_export("BINANCE:BTCUSDT"))
```

---

## See Also

- [Streaming vs Historical](../concepts/streaming-vs-historical.md) — when to use streaming vs historical
- [Historical Data guide](historical-data.md) — backfilling missed bars with `get_historical_ohlcv()`
- [Macro Indicators guide](macro-indicators.md) — streaming macro indicators (INDEX:NDFI, USI:PCC)
- [OHLCV reference](../reference/chart/ohlcv.md) — full method signatures
