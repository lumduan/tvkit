# Quickstart

Four self-contained examples — each under 15 lines. Pick the one that matches your use case.

## 1. Fetch Historical OHLCV Bars

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def main() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=5)
    for bar in bars:
        print(f"{bar.timestamp}  close={bar.close:.2f}")

asyncio.run(main())
```

## 2. Stream Real-time Bars

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def main() -> None:
    async with OHLCV() as client:
        count = 0
        async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="1"):
            print(f"BTC close={bar.close:,.2f}")
            count += 1
            if count >= 3:
                break

asyncio.run(main())
```

## 3. Scan a Market

```python
import asyncio
from tvkit.api.scanner import ScannerService, Market, create_comprehensive_request

async def main() -> None:
    service = ScannerService()
    request = create_comprehensive_request(sort_by="market_cap_basic", sort_order="desc", range_end=5)
    response = await service.scan_market(Market.US, request)
    for stock in response.data:
        print(f"{stock.name}  ${stock.close}  cap={stock.market_cap_basic:,.0f}")

asyncio.run(main())
```

## 4. Export to CSV

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def main() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=30)
    path = await DataExporter().to_csv(bars, "./aapl_30d.csv")
    print(f"Saved: {path}")

asyncio.run(main())
```

---

## Running the Examples

```bash
# Save any example above as main.py, then run:
uv run python main.py

# Or with pip:
python main.py
```

---

## Next Steps

[Your First Script →](first-script.md) — an annotated walkthrough explaining each step
