# Fundamentals Models Reference

**Module:** `tvkit.api.fundamentals`
**Available since:** v0.12.0

Pydantic models returned by [`FundamentalsClient`](client.md). Values are raw reporting-currency units. `None` in a value list means the field was not reported for that period — never zero.

## Import

```python
from tvkit.api.fundamentals import (
    FinancialStatement,
    StatementLine,
    FiscalPeriod,
    SegmentReport,
    SegmentPeriod,
    RevenueSegment,
    DividendReport,
    DividendEvent,
    EarningsReport,
    EarningsPeriod,
    FundamentalsSnapshot,
)
```

## Type Definitions

### `FiscalPeriod`

| Field | Type | Description |
|-------|------|-------------|
| `label` | `str` | Period label, e.g. `"2025"` (FY) or `"2026-Q3"` (FQ). |
| `period_end` | `datetime \| None` | Period end as an aware UTC datetime, or `None`. |
| `period_type` | `Period` | The period type this label belongs to. |

### `StatementLine`

| Field | Type | Description |
|-------|------|-------------|
| `field_id` | `str` | TradingView field-id base, e.g. `"total_revenue"`. |
| `label` | `str` | Human-readable row label from the field catalog. |
| `values` | `list[float \| None]` | Values index-aligned to the statement periods; `None` = not reported. |

### `FinancialStatement`

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Normalized `EXCHANGE:TICKER` symbol. |
| `statement` | `StatementType` | Which statement family this is. |
| `period_type` | `Period` | Period type of the columns. |
| `currency` | `str \| None` | Reporting currency code (e.g. `"THB"`). |
| `report_template` | `str \| None` | Issuer template: `industrial` / `banking` / `insurance` / `other`. |
| `periods` | `list[FiscalPeriod]` | Reporting periods, newest-first. |
| `lines` | `list[StatementLine]` | Statement rows in display order. |

Method: `line(field_id: str) -> StatementLine | None` — the row with `field_id`, or `None` if the issuer did not report it.

### `RevenueSegment`

| Field | Type | Description |
|-------|------|-------------|
| `label` | `str` | Segment label as delivered (localized), e.g. `"Airport"`. |
| `value` | `float \| None` | Revenue in raw currency units. |

### `SegmentPeriod`

| Field | Type | Description |
|-------|------|-------------|
| `period` | `FiscalPeriod` | The fiscal period. |
| `segments` | `list[RevenueSegment]` | Segment cells for this period. |

### `SegmentReport`

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Normalized `EXCHANGE:TICKER` symbol. |
| `currency` | `str \| None` | Reporting currency code. |
| `by_business` | `list[SegmentPeriod]` | Revenue by business/source, newest-first. |
| `by_region` | `list[SegmentPeriod]` | Revenue by country/region, newest-first. |

### `DividendEvent`

| Field | Type | Description |
|-------|------|-------------|
| `amount` | `float \| None` | Dividend per share. |
| `ex_date` | `datetime \| None` | Ex-dividend date (UTC). |
| `payment_date` | `datetime \| None` | Payment date (UTC). |
| `record_date` | `datetime \| None` | Record date (UTC). |
| `dividend_type` | `str \| None` | e.g. `"Annual"`, `"Quarterly"`. |

### `DividendReport`

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Normalized `EXCHANGE:TICKER` symbol. |
| `currency` | `str \| None` | Reporting currency code. |
| `events` | `list[DividendEvent]` | Dividend events, newest-first. |
| `yield_recent` | `float \| None` | Most recent dividend yield (%). |
| `payout_ratio_ttm` | `float \| None` | Payout ratio, TTM (%). |
| `dividends_paid` | `float \| None` | Total dividends paid (raw currency, most recent period). |

### `EarningsPeriod`

| Field | Type | Description |
|-------|------|-------------|
| `label` | `str` | Fiscal period label. |
| `eps_reported` | `float \| None` | Reported EPS. |
| `eps_estimate` | `float \| None` | Consensus EPS estimate. |
| `eps_surprise_pct` | `float \| None` | EPS surprise vs estimate, percent. |
| `revenue_reported` | `float \| None` | Reported revenue (raw). |
| `revenue_estimate` | `float \| None` | Revenue estimate (raw). |

### `EarningsReport`

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Normalized `EXCHANGE:TICKER` symbol. |
| `currency` | `str \| None` | Reporting currency code. |
| `period_type` | `Period` | `FY` or `FQ`. |
| `periods` | `list[EarningsPeriod]` | Earnings periods, newest-first. |

### `FundamentalsSnapshot`

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Normalized `EXCHANGE:TICKER` symbol. |
| `currency` | `str \| None` | Reporting currency code. |
| `income` | `FinancialStatement \| None` | Income statement. |
| `balance` | `FinancialStatement \| None` | Balance sheet. |
| `cash_flow` | `FinancialStatement \| None` | Cash-flow statement. |
| `statistics` | `FinancialStatement \| None` | Statistics/ratios. |
| `segments` | `SegmentReport \| None` | Revenue segments. |
| `dividends` | `DividendReport \| None` | Dividend history. |
| `earnings` | `EarningsReport \| None` | Earnings vs estimates. |
| `raw` | `dict[str, Any]` | Raw merged quote field dict (unparsed). |

## See Also

- [Client](client.md) — the methods that return these models
- [Financial Statements Concept](../../concepts/financial-statements.md)
