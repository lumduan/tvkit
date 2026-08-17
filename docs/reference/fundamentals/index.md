# Fundamentals API Reference

**Module:** `tvkit.api.fundamentals`
**Available since:** v0.12.0

Async client for TradingView financial statements and revenue segments over the WebSocket quote protocol. Anonymous by default.

## Import

```python
from tvkit.api.fundamentals import (
    FundamentalsClient,
    Period,
    StatementType,
    FinancialStatement,
    SegmentReport,
    DividendReport,
    EarningsReport,
    FundamentalsSnapshot,
    FundamentalsError,
    NoFundamentalDataError,
)
```

## Module Layout

| Symbol | Kind | Reference |
|--------|------|-----------|
| `FundamentalsClient` | Async context-managed client | [Client](client.md) |
| `Period`, `StatementType` | Enums | [Client](client.md) |
| `FinancialStatement`, `StatementLine`, `FiscalPeriod` | Statement models | [Models](models.md) |
| `SegmentReport`, `SegmentPeriod`, `RevenueSegment` | Segment models | [Models](models.md) |
| `DividendReport`, `DividendEvent` | Dividend models | [Models](models.md) |
| `EarningsReport`, `EarningsPeriod` | Earnings models | [Models](models.md) |
| `FundamentalsSnapshot` | Bundle model | [Models](models.md) |
| `FundamentalsError` and subclasses | Exceptions | [Client](client.md) |

## Quick Example

```python
import asyncio
from tvkit.api.fundamentals import FundamentalsClient, Period

async def main() -> None:
    async with FundamentalsClient() as fx:
        segments = await fx.get_segments("SET:AOT")
        income = await fx.get_income_statement("NASDAQ:AAPL", period=Period.FY)
        print(segments.by_business[0].period.label, income.currency)

asyncio.run(main())
```

## Reference Pages

- [Client](client.md) — `FundamentalsClient`, `Period`, `StatementType`, exceptions
- [Models](models.md) — statement, segment, dividend, earnings, and snapshot models

## See Also

- [Fundamentals Guide](../../guides/fundamentals.md) — task-oriented walk-through
- [Financial Statements Concept](../../concepts/financial-statements.md) — field catalog and period semantics
- [DataExporter](../export/exporter.md) — export fundamentals to Polars / CSV / JSON
