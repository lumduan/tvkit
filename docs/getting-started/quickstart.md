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

**Output:**

| timestamp | date | close |
|---|---|---|
| 1786455000.0 | 2026-08-11 | 304.91 |
| 1786541400.0 | 2026-08-12 | 302.25 |
| 1786627800.0 | 2026-08-13 | 305.26 |
| 1786714200.0 | 2026-08-14 | 305.93 |
| 1786973400.0 | 2026-08-17 | 305.59 |

# 5 rows total, showing 5
# `date` is derived — OHLCVBar has 6 fields: timestamp, open, high, low, close, volume

*Example output — live market values will differ.*

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

**Output:**

```text
BTC close=64,153.07
BTC close=64,147.20
BTC close=64,145.64
```

## 3. Scan a Market

```python
import asyncio
from tvkit.api.scanner import ScannerService, Market, create_comprehensive_request

async def main() -> None:
    service = ScannerService()
    request = create_comprehensive_request(sort_by="market_cap_basic", sort_order="desc", range_end=5)
    response = await service.scan_market(Market.AMERICA, request)
    for stock in response.data:
        print(f"{stock.name}  ${stock.close}  cap={stock.market_cap_basic:,.0f}")

asyncio.run(main())
```

**Output:**

| name | close | market_cap_basic |
|---|---|---|
| NVDA | 225.01 | 5,445,242,088,564 |
| AAPL | 305.59 | 4,459,835,263,931 |
| GOOG | 341.45 | 4,191,656,347,478 |
| MSFT | 480.35 | 3,566,860,693,823 |
| AMZN | 261.31 | 2,818,571,764,248 |

# 5 rows returned of total_count=4943, limited by range_end=5
# StockData carries 20 declared fields; `create_comprehensive_request` requests 101 columns

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

**Output:**

```text
Saved: aapl_30d.csv
```

`to_csv` also writes a sidecar `aapl_30d.metadata.txt`. The first rows of `aapl_30d.csv`:

```text
timestamp,open,high,low,close,volume
2026-07-07T13:30:00+00:00,315.29,315.48,310.15,310.66,42490002.0
2026-07-08T13:30:00+00:00,311.91,314.82,307.05,313.39,41323480.0
2026-07-09T13:30:00+00:00,310.51,316.53,308.16,316.22,48124490.0
...
```

# 30 data rows total, showing 3; `timestamp` is written as an ISO-8601 string

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
