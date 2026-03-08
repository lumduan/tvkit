# Streaming vs Historical Data

[Home](../index.md) > Concepts > Streaming vs Historical Data

tvkit provides two ways to access market data:

- **Historical queries** — fetch a fixed set of past bars in one call
- **Streaming subscriptions** — receive bars continuously as they form

## Decision Table

| Use Case | Recommended Method | Why |
|----------|--------------------|-----|
| Backtest on past data | `get_historical_ohlcv()` | Returns complete closed bars for a date range or bar count |
| Train an ML model | `get_historical_ohlcv()` | Deterministic, reproducible dataset |
| Display a chart | `get_historical_ohlcv()` | Consistent snapshot of N bars |
| Export OHLCV dataset | `get_historical_ohlcv()` | Fetches a fixed dataset suitable for saving to CSV or JSON |
| Monitor live prices | `get_ohlcv()` | Streams bars as they close via WebSocket |
| Trigger on price events | `get_ohlcv()` | Low-latency update as each bar forms |
| Real-time portfolio tracking | `get_latest_trade_info()` | Multi-symbol trade updates in one stream |
| Get a single current quote | `get_quote_data()` | Single-shot quote without a streaming loop |

## Key Differences

| Property | `get_historical_ohlcv()` | `get_ohlcv()` |
|----------|--------------------------|---------------|
| Return type | `list[OHLCV]` — all bars at once | `AsyncGenerator[OHLCV, None]` — one bar per yield |
| Connection | Opens, fetches, closes | Stays open until you break or cancel |
| Latency | One round-trip (~100–500ms) | Each bar delivered as it closes (<50ms) |
| Data completeness | All requested bars guaranteed | Bars may be skipped if connection drops — backfill with `get_historical_ohlcv()` |
| Bar state | All bars are closed (final) | Latest bar may still be forming (updates until close) |
| Suitable for | Analysis, backtesting, export | Alerting, dashboards, signal generation |

## Data Flow Model

```text
Historical query:
Client ──request──▶ TradingView ──N bars──▶ Client (connection closes)

Streaming subscription:
Client ──subscribe──▶ TradingView ──bar──▶ ──bar──▶ ──bar──▶ ...
                                  (connection stays open)
```

## Latency Comparison

Historical fetch latency is dominated by the round-trip time to TradingView's WebSocket endpoint — typically **100–500ms** per request, independent of bar count.

Real-time streaming latency is the time between a bar closing on the exchange and tvkit yielding it — typically **under 50ms**.

## Data Volume Considerations

Historical requests are bounded by `MAX_BARS_REQUEST` per call. If you need more bars than the limit, use the `start`/`end` date-range parameters to fetch in segments.

Streaming has no bar-count limit per session, but bars accumulate in memory if you store them without flushing. Flush periodically:

```python
bars: list = []

async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="1"):
    bars.append(bar)
    if len(bars) > 10_000:
        await save_to_disk(bars)
        bars.clear()
```

## Combining Both Methods

The most common production pattern combines both APIs:

1. Fetch recent history to seed your dataset
2. Start a live stream to receive new bars as they close
3. Append each new bar to the history list

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def seed_and_stream(symbol: str, interval: str) -> None:
    async with OHLCV() as client:
        # 1. Seed with recent history
        bars = await client.get_historical_ohlcv(symbol, interval, bars_count=500)
        print(f"Loaded {len(bars)} historical bars")

        # 2. Stream new bars and append
        async for bar in client.get_ohlcv(symbol, interval=interval):
            bars.append(bar)
            print(f"Live bar: {bar.timestamp} close={bar.close}")

asyncio.run(seed_and_stream("BINANCE:BTCUSDT", "1"))
```

## See Also

- [Historical Data guide](../guides/historical-data.md) — count mode, date-range mode, and `MAX_BARS_REQUEST`
- [Real-time Streaming guide](../guides/realtime-streaming.md) — connection management and multiple symbol monitoring
- [Symbols](symbols.md) — symbol format shared by both access patterns
- [Intervals](intervals.md) — timeframe strings used by both methods
