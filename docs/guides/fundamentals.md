# Fundamentals Guide

[Home](../index.md) > Guides > Fundamentals

Retrieve financial statements and revenue segments for any symbol with `FundamentalsClient`.

## Prerequisites

- tvkit installed (`uv add tvkit` or `pip install tvkit`)
- No login required — fundamentals work anonymously

## When to Use the Fundamentals API

Use `FundamentalsClient` when you need per-symbol financial data: the income statement, balance sheet, cash-flow statement, statistics/ratios, dividends, earnings estimates, or revenue segments. For screening many symbols by a single snapshot metric, use the [Scanner](scanner.md) instead.

## Data Flow

```text
FundamentalsClient
      │  (one WebSocket per call — the server closes a quote socket after one snapshot)
      ▼
wss://data.tradingview.com  ──quote_set_fields──▶  qsd frames  ──▶  parsed models
```

## Revenue Segments

```python
import asyncio
from tvkit.api.fundamentals import FundamentalsClient

async def main() -> None:
    async with FundamentalsClient() as fx:
        report = await fx.get_segments("SET:AOT")
        latest = report.by_business[0]
        print(f"{report.symbol} {latest.period.label} ({report.currency})")
        for seg in latest.segments:
            print(f"  {seg.label}: {seg.value}")

asyncio.run(main())
```

Segment labels are issuer-specific and localized (set `language=` on the client). Values are raw currency units.

## Financial Statements

```python
from tvkit.api.fundamentals import FundamentalsClient, Period

async with FundamentalsClient() as fx:
    income = await fx.get_income_statement("NASDAQ:AAPL", period=Period.FY, max_periods=5)
    years = [p.label for p in income.periods]
    print("Currency:", income.currency, "Columns:", years)
    revenue = income.line("total_revenue")
    if revenue is not None:
        print("Total revenue:", revenue.values)
```

Rows are ordered as the TradingView UI shows them. A line the issuer's template omits (for example, cost of goods for a bank) is simply absent — use `statement.line(field_id)` and check for `None`. Values align to `statement.periods` by index.

`get_balance_sheet()`, `get_cash_flow()`, and `get_statistics()` follow the same shape.

## Everything at Once

```python
async with FundamentalsClient() as fx:
    snapshot = await fx.get_financials("NASDAQ:AAPL")
    print(snapshot.income.currency)
    print(snapshot.segments.by_region[0].segments)
    print(snapshot.dividends.yield_recent)
    print(snapshot.earnings.periods[0].eps_surprise_pct)
```

`get_financials()` fetches income, balance, cash flow, statistics, segments, dividends, and earnings in one WebSocket round-trip.

## Exporting

```python
from tvkit.export import DataExporter, ExportFormat

async with FundamentalsClient() as fx:
    snapshot = await fx.get_financials("SET:AOT")

exporter = DataExporter()
result = await exporter.export_fundamentals_data(snapshot, ExportFormat.POLARS)
df = result.data  # tidy/long: symbol, dataset, row, label, period, period_end, value, currency

# or write a file directly
await exporter.export_fundamentals_data(snapshot, ExportFormat.CSV, "aot_financials.csv")
```

## Authenticated Sessions

Anonymous access already returns the full statement history. To use a logged-in session anyway:

```python
from tvkit.auth import TradingViewCredentials

creds = TradingViewCredentials(browser="chrome")
async with FundamentalsClient(credentials=creds) as fx:
    ...
```

## See Also

- [Fundamentals Reference](../reference/fundamentals/index.md)
- [Financial Statements Concept](../concepts/financial-statements.md)
- [Exporting Guide](exporting.md)
