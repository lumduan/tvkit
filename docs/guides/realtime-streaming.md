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

**Output:**

```text
close=64211.63  volume=4
close=64215.76  volume=2
close=64226.30  volume=5
close=64202.81  volume=8
...
```

The loop never ends on its own. `volume` is small because BTC 1-minute volume is denominated in
BTC and `:,.0f` rounds it to whole units.

*Example output — live market values will differ.*

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
from tvkit.api.chart.models.ohlcv import OHLCVBar

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
        "FX_IDC:EURUSD",
        "OANDA:XAUUSD",
        "INDEX:NDFI",
        "USI:PCC",
    ]

    async with OHLCV() as client:
        async for trade_info in client.get_latest_trade_info(symbols):
            print(f"Update: {trade_info}")

asyncio.run(monitor_portfolio())
```

**Output:**

```text
Update: {'session_id': '0.9329114.0_hkg1-charts-free-3-tvbs-53vcz-2', 'timestamp': 1787032586,
         'timestampMs': 1787032586882, 'release': 'release_209-23', 'protocol': 'json', ...}
Update: {'m': 'qsd', 'p': ['qs_afcyponiwryy', {'n': '={"adjustment":"splits",...,"symbol":"BINANCE:BTCUSDT"}',
         's': 'ok', 'v': {'pro_name': 'BINANCE:BTCUSDT', 'lp': 64151.901279000005, 'ch': -309.87,
         'chp': -0.48, 'volume': 3547.22502, 'short_name': 'BTCUSDT', 'type': 'spot', ...}}]}
Update: {'m': 'qsd', 'p': ['qs_afcyponiwryy', {'n': 'OANDA:XAUUSD', 's': 'ok',
         'v': {'pro_name': 'OANDA:XAUUSD', 'lp': 4396.09, 'ch': -20.59, 'chp': -0.47,
         'volume': 171265.0, 'short_name': 'XAUUSD', 'type': 'commodity', ...}}]}
...
```

# dict keys elided with `...`; the real frames carry ~18 keys under `v`

`get_latest_trade_info()` yields **raw protocol dicts**, not `OHLCVBar` objects. The first frame is
the connection handshake; subsequent frames are `qsd` quote updates, one per symbol. The last price
is at `p[1]["v"]["lp"]`. A symbol the server rejects arrives as a frame with
`'s': 'error', 'errmsg': 'no_such_symbol'` rather than raising.

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

## Automatic Reconnection

`OHLCV` reconnects automatically when the WebSocket closes unexpectedly. No changes to existing call sites are required — reconnection is on by default.

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def main() -> None:
    async with OHLCV() as client:
        # Reconnection is automatic with default settings (5 attempts, 1s–30s backoff).
        # Transient network disruptions are handled transparently.
        async for bar in client.get_ohlcv("NASDAQ:AAPL", "1D"):
            print(bar.close)

asyncio.run(main())
```

**Output:**

```text
309.38
311.0
312.41
313.33
...
```

### Default Retry Behaviour

| Parameter | Default | Description |
| --- | --- | --- |
| `max_attempts` | `5` | Total connection attempts before giving up |
| `base_backoff` | `1.0s` | Base delay, doubles each attempt |
| `max_backoff` | `30.0s` | Maximum delay cap |

### Custom Retry Configuration

Override the defaults for long-running pipelines that require higher resilience:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def main() -> None:
    async with OHLCV(
        max_attempts=10,
        base_backoff=2.0,
        max_backoff=60.0,
    ) as client:
        async for bar in client.get_ohlcv("NASDAQ:AAPL", "1D"):
            print(bar.close)

asyncio.run(main())
```

**Output:**

```text
309.38
311.0
312.41
313.33
...
```

Identical to the default configuration while the connection holds — the retry settings only
change behaviour after a disconnect.

### Handling Attempt Exhaustion

After all attempts fail, `StreamConnectionError` is raised. Catch it to alert, fall back, or exit cleanly:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.chart.exceptions import StreamConnectionError

async def main() -> None:
    try:
        async with OHLCV(max_attempts=3) as client:
            async for bar in client.get_ohlcv("NASDAQ:AAPL", "1D"):
                print(bar.close)
    except StreamConnectionError as exc:
        print(f"Stream permanently disconnected after {exc.attempts} attempts: {exc}")
        # Alert, write to dead-letter queue, or exit

asyncio.run(main())
```

**Output:**

```text
309.38
311.0
312.41
313.33
...
```

That is the healthy path. Only after 3 failed attempts does the `except` branch run:

```text
Stream permanently disconnected after 3 attempts: WebSocket reconnection failed after 3 attempts.
```

`exc.last_error` holds the underlying `TimeoutError`/`OSError`/`WebSocketException` when one was
captured, or `None`.

If bars were missed during a disconnect, backfill the gap using `get_historical_ohlcv()` before resuming the live stream.

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
from tvkit.api.chart.models.ohlcv import OHLCVBar
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

**Output:**

Nothing is printed — the observable effect is on disk. After the first flush, `./export/` holds:

```text
export/BINANCE_BTCUSDT.csv           (386 bytes)
export/BINANCE_BTCUSDT.metadata.txt  (378 bytes)
```

with the CSV containing one row per buffered bar:

```text
timestamp,open,high,low,close,volume
2026-08-18T05:49:00+00:00,64215.75,64226.31,64215.75,64226.3,4.99708
2026-08-18T05:50:00+00:00,64226.31,64226.31,64202.81,64202.81,8.26398
2026-08-18T05:51:00+00:00,64202.81,64202.82,64200.08,64200.08,2.02024
...
```

# captured with flush_every=5 so the run finished quickly; flush_every=100 behaves identically
# `to_csv` overwrites the file on each flush — append or rotate filenames to retain history
# `./export/` must already exist

---

## See Also

- [Streaming vs Historical](../concepts/streaming-vs-historical.md) — when to use streaming vs historical
- [Historical Data guide](historical-data.md) — backfilling missed bars with `get_historical_ohlcv()`
- [Macro Indicators guide](macro-indicators.md) — streaming macro indicators (INDEX:NDFI, USI:PCC)
- [OHLCV reference](../reference/chart/ohlcv.md) — full method signatures
