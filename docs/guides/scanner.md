# Scanner Guide

[Home](../index.md) > Guides > Scanner

The scanner API lets you screen stocks across **69 global markets** using **100+ financial metrics**. It returns a ranked list of stocks matching your criteria as a structured response object (`response.data`) — no WebSocket connection required.

## Prerequisites

- tvkit installed: see [Installation](../getting-started/installation.md)
- Understand column sets: see [Scanner Column Sets](../concepts/scanner-columns.md)

---

## When to Use the Scanner API

The scanner is useful for:

- Screening stocks based on fundamentals or technical indicators
- Finding top movers by market cap, volume, or momentum
- Ranking stocks within a market or region
- Building watchlists or investment universes for systematic strategies

tvkit does not send filter criteria to TradingView — a request selects columns, a sort order and a
row range. Narrow the result set with `sort_by` / `range_end`, then filter the returned
`list[StockData]` in Python.

---

## Data Flow

```text
Your code
    │
    │  scan_market(market, request)
    ▼
tvkit ScannerService
    │
    │  HTTP request
    ▼
TradingView Scanner API
    │
    ▼
Ranked stock results (response.data)
```

---

## Basic Scan

Scan a single market and retrieve the top stocks by market cap:

```python
import asyncio
from tvkit.api.scanner import ScannerService, Market
from tvkit.api.scanner import create_comprehensive_request

async def scan_us_market() -> None:
    service = ScannerService()

    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=10,
    )

    response = await service.scan_market(Market.AMERICA, request)

    for stock in response.data:
        print(f"{stock.name:12s}  price={stock.close}  market_cap={stock.market_cap_basic:,.0f}")

asyncio.run(scan_us_market())
```

**Output:**

| name | close | market_cap_basic |
|---|---|---|
| NVDA | 225.01 | 5,445,242,088,564 |
| AAPL | 305.59 | 4,459,835,263,931 |
| GOOG | 341.45 | 4,191,656,347,478 |
| MSFT | 480.35 | 3,566,860,693,823 |
| AMZN | 261.31 | 2,818,571,764,248 |

# 10 rows total, showing 5 — `total_count` reports 4943 matching symbols

*Example output — live market values will differ.*

`Market.AMERICA` covers both NASDAQ and NYSE. `range_end=10` returns the top 10 results.

---

## Sorting and Pagination

Control result ordering and page through large result sets:

```python
request = create_comprehensive_request(
    sort_by="price_earnings_ttm",  # sort by P/E ratio
    sort_order="asc",              # lowest P/E first
    range_start=0,                 # offset (0-based)
    range_end=25,                  # fetch 25 results
)
```

Increment `range_start` by `range_end` to page through results:

```python
from tvkit.api.scanner import ScannerService, Market
from tvkit.api.scanner.models.scanner import StockData

async def paginate_scan(market: Market, page_size: int = 25) -> list[StockData]:
    service = ScannerService()
    all_stocks: list[StockData] = []
    offset = 0

    while True:
        request = create_comprehensive_request(
            sort_by="market_cap_basic",
            sort_order="desc",
            range_start=offset,
            range_end=offset + page_size,
        )
        response = await service.scan_market(market, request)
        if not response.data:
            break
        all_stocks.extend(response.data)
        offset += page_size

    return all_stocks
```

---

## Regional Scanning

Some workflows require scanning multiple exchanges within a geographic region. The `get_markets_by_region()` helper returns all markets belonging to a region:

```python
import asyncio
from tvkit.api.scanner import ScannerService, MarketRegion
from tvkit.api.scanner import create_comprehensive_request, get_markets_by_region

async def scan_asia_pacific() -> None:
    service = ScannerService()
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=5,
    )

    asia_markets = get_markets_by_region(MarketRegion.ASIA_PACIFIC)

    for market in asia_markets:
        response = await service.scan_market(market, request)
        if response.data:
            top = response.data[0]
            print(f"{market.value:15s}  leader={top.name}  cap={top.market_cap_basic:,.0f}")

asyncio.run(scan_asia_pacific())
```

**Output:**

| market | leader | market_cap_basic |
|---|---|---|
| australia | BHP | 311,700,320,153 |
| bangladesh | GP | 337,980,106,342 |
| china | 688825 | 3,690,487,319,188 |
| hongkong | 700 | 3,968,954,687,500 |
| indonesia | BBCA | 782,796,547,656,250 |

# 17 markets in ASIA_PACIFIC, showing 5
# caps are in each market's own reporting currency — IDR and KRW are not comparable to USD

Available regions: `GLOBAL`, `NORTH_AMERICA`, `EUROPE`, `MIDDLE_EAST_AFRICA`, `MEXICO_SOUTH_AMERICA`, `ASIA_PACIFIC`.

---

## Performance Notes

Scanner queries are stateless HTTP requests. For large-scale scans:

- Use pagination (`range_start`, `range_end`) rather than requesting thousands of rows at once
- Cache results locally when scanning multiple regions — TradingView rate limits repeated requests
- Prefer smaller column sets (e.g., `BASIC`) when you only need price data; avoid `COMPREHENSIVE_FULL` unless necessary

---

## Available Markets

The `Market` enum includes 69 exchanges across five global regions. Examples:

| Region | Market Enum | Exchange(s) |
|--------|------------|-------------|
| North America | `Market.AMERICA` | NASDAQ, NYSE |
| North America | `Market.CANADA` | TSX, TSXV |
| Europe | `Market.GERMANY` | XETRA |
| Europe | `Market.UK` | LSE |
| Asia Pacific | `Market.JAPAN` | TSE |
| Asia Pacific | `Market.THAILAND` | SET |
| Asia Pacific | `Market.SINGAPORE` | SGX |
| Middle East | `Market.UAE` | ADX, DFM |
| Latin America | `Market.BRAZIL` | B3 |

See [Markets reference](../reference/scanner/markets.md) for the full list of 69 markets.

---

## See Also

- [Scanner Column Sets](../concepts/scanner-columns.md) — choosing the right column set
- [Exporting Data guide](exporting.md) — saving scanner results to CSV, JSON, or Polars
- [Scanner API reference](../reference/scanner/scanner.md) — full request specification
- [Markets reference](../reference/scanner/markets.md) — complete market list
