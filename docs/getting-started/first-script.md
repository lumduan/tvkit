# Your First Script

This page walks through a complete tvkit script step by step. By the end, you will understand the basic structure used in most tvkit programs.

## What the Script Does

1. Opens a WebSocket connection to TradingView
2. Fetches the last 5 daily bars for Apple and Bitcoin
3. Prints the date and closing price for each bar
4. Closes the connection cleanly

## The Script

Create a file called `first_script.py`:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.utils import convert_timestamp_to_iso

async def main() -> None:
    # Open a managed WebSocket connection.
    # The connection closes automatically when the `async with` block exits.
    async with OHLCV() as client:

        # Fetch 5 daily bars for Apple.
        # bars_count=5 returns the 5 most recent closed bars.
        apple_bars = await client.get_historical_ohlcv(
            exchange_symbol="NASDAQ:AAPL",
            interval="1D",
            bars_count=5,
        )

        # Fetch 5 daily bars for Bitcoin.
        btc_bars = await client.get_historical_ohlcv(
            exchange_symbol="BINANCE:BTCUSDT",
            interval="1D",
            bars_count=5,
        )

    # Print Apple bars.
    # Each bar has: timestamp (Unix, UTC), open, high, low, close, volume.
    print("Apple (AAPL) — last 5 daily closes:")
    for bar in apple_bars:
        date = convert_timestamp_to_iso(bar.timestamp)[:10]  # "YYYY-MM-DD"
        print(f"  {date}  ${bar.close:.2f}")

    # Print Bitcoin bars.
    print("\nBitcoin (BTCUSDT) — last 5 daily closes:")
    for bar in btc_bars:
        date = convert_timestamp_to_iso(bar.timestamp)[:10]
        print(f"  {date}  ${bar.close:,.2f}")

# asyncio.run() starts the async event loop — required to run async tvkit code.
if __name__ == "__main__":
    asyncio.run(main())
```

## Run It

```bash
# With uv
uv run python first_script.py

# With pip
python first_script.py
```

## Expected Output

```text
Apple (AAPL) — last 5 daily closes:
  2026-08-11  $304.91
  2026-08-12  $302.25
  2026-08-13  $305.26
  2026-08-14  $305.93
  2026-08-17  $305.59

Bitcoin (BTCUSDT) — last 5 daily closes:
  2026-08-14  $63,043.56
  2026-08-15  $63,086.01
  2026-08-16  $62,900.00
  2026-08-17  $64,532.10
  2026-08-18  $64,135.70
```

*Example output — live market values will differ.*

## Key Concepts Used

| Element | What It Is |
|---------|-----------|
| `async with OHLCV()` | Context manager that opens and closes the WebSocket connection |
| `await client.get_historical_ohlcv()` | Async call that returns a `list[OHLCVBar]` |
| `exchange_symbol="NASDAQ:AAPL"` | Exchange prefix + ticker in colon format — see [Symbols](../concepts/symbols.md) |
| `interval="1D"` | TradingView interval string — see [Intervals](../concepts/intervals.md) |
| `bars_count=5` | Number of most recent bars to fetch |
| `bar.timestamp` | Unix timestamp (seconds, UTC) — convert with `convert_timestamp_to_iso()` |
| `asyncio.run(main())` | Starts the async event loop — required to run async tvkit code |

## Next Steps

- [Historical Data guide](../guides/historical-data.md) — date-range mode, MAX_BARS_REQUEST, Polars export
- [Real-time Streaming guide](../guides/realtime-streaming.md) — live bar streaming with `get_ohlcv()`
- [Scanner guide](../guides/scanner.md) — screen stocks across 69 global markets
