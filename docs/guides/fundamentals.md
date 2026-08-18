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

**Output:**

```text
SET:AOT 2025 (THB)
  Airport: 62432730000.0
  Ground Aviation Services: 3545640000.0
  Hotel: 671470000.0
  Security: 22990000.0
```

The same figures as the TradingView UI renders them:

| Segment | 2025 |
|---|---|
| Airport | 62.43B |
| Ground Aviation Services | 3.55B |
| Hotel | 671.47M |
| Security | 22.99M |

Sanity: Σ(2025 by-business) = 66.67B ≈ total revenue 66.68B → segment values are
**raw reporting-currency units (THB), full precision**; only the table above abbreviates K/M/B.

*Example output — reported figures change with each filing.*

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

**Output:**

```text
Currency: USD Columns: ['2025', '2024', '2023', '2022', '2021']
Total revenue: [416161000000.0, 391035000000.0, 383285000000.0, 394328000000.0, 365817000000.0]
```

| Row | 2025 | 2024 | 2023 | 2022 | 2021 |
|---|---|---|---|---|---|
| Total revenue | 416.16B (+6.43%) | 391.04B (+2.02%) | 383.29B (−2.80%) | 394.33B (+7.79%) | 365.82B |

# periods are newest-first; `values` is index-aligned to `statement.periods`
# `income.report_template` is `'industrial'` for AAPL; the first six line labels are
#   Total revenue, Cost of goods sold, Gross profit, Operating expenses (excl. COGS),
#   Operating income, Non-operating income (total)

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

**Output:**

```text
USD
[RevenueSegment(label='United States', value=151790000000.0), RevenueSegment(label='Europe', value=111032000000.0), RevenueSegment(label='Greater China', value=64377000000.0), RevenueSegment(label='Rest of Asia Pacific', value=33696000000.0), RevenueSegment(label='Japan', value=28703000000.0), RevenueSegment(label='Americas', value=26563000000.0)]
0.353021933121956
1.0590062675549348
```

# `yield_recent` and `eps_surprise_pct` are percentages, not fractions
# `snapshot.raw` is populated but has `repr=False`, so `print(snapshot)` omits it while
#   `snapshot.model_dump()` includes it

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

**Output:**

```text
shape: (1689, 8)
┌─────────┬─────────┬───────────────┬───────────────┬────────┬─────────────────────────┬───────────┬──────────┐
│ symbol  ┆ dataset ┆ row           ┆ label         ┆ period ┆ period_end              ┆ value     ┆ currency │
│ ---     ┆ ---     ┆ ---           ┆ ---           ┆ ---    ┆ ---                     ┆ ---       ┆ ---      │
│ str     ┆ str     ┆ str           ┆ str           ┆ str    ┆ str                     ┆ f64       ┆ str      │
╞═════════╪═════════╪═══════════════╪═══════════════╪════════╪═════════════════════════╪═══════════╪══════════╡
│ SET:AOT ┆ income  ┆ total_revenue ┆ Total revenue ┆ 2025   ┆ 2025-09-30T00:00:00+00… ┆ 6.6679e10 ┆ THB      │
│ SET:AOT ┆ income  ┆ total_revenue ┆ Total revenue ┆ 2024   ┆ 2024-09-30T00:00:00+00… ┆ 6.7121e10 ┆ THB      │
│ SET:AOT ┆ income  ┆ total_revenue ┆ Total revenue ┆ 2023   ┆ 2023-09-30T00:00:00+00… ┆ 4.8141e10 ┆ THB      │
│ SET:AOT ┆ income  ┆ total_revenue ┆ Total revenue ┆ 2022   ┆ 2022-09-30T00:00:00+00… ┆ 1.6560e10 ┆ THB      │
│ SET:AOT ┆ income  ┆ total_revenue ┆ Total revenue ┆ 2021   ┆ 2021-09-30T00:00:00+00… ┆ 7.0856e9  ┆ THB      │
└─────────┴─────────┴───────────────┴───────────────┴────────┴─────────────────────────┴───────────┴──────────┘
```

# 1689 rows total, showing 5 — one row per (line, period)
# `period_end` is a String, `value` is a nullable Float64
# `dataset` takes exactly these values, in this order:
#   income, balance, cash_flow, statistics, segment_business, segment_region, dividend, earnings

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
