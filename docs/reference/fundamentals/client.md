# FundamentalsClient Reference

**Module:** `tvkit.api.fundamentals`
**Available since:** v0.12.0

Async context manager that retrieves per-symbol financial statements and revenue segments over TradingView's WebSocket quote protocol.

## Import

```python
from tvkit.api.fundamentals import FundamentalsClient, Period, StatementType
from tvkit.auth import TradingViewCredentials  # optional, for authenticated sessions
```

## `FundamentalsClient`

Opens a fresh short-lived WebSocket per call (the TradingView server closes a quote socket after one snapshot); the authenticated session, when used, is established once for the block.

### Signature

```python
class FundamentalsClient:
    def __init__(
        self,
        credentials: TradingViewCredentials | None = None,
        language: str = "en",
        timeout: float = 30.0,
        ws_url: str = "wss://data.tradingview.com/socket.io/websocket?from=chart%2F",
    ) -> None: ...
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `credentials` | `TradingViewCredentials \| None` | `None` | Authentication credentials. `None` is anonymous, which is sufficient for fundamentals. |
| `language` | `str` | `"en"` | Locale sent via `set_locale`; controls segment-label localization. |
| `timeout` | `float` | `30.0` | Seconds to wait for a snapshot to complete. |
| `ws_url` | `str` | data socket URL | WebSocket endpoint override. |

### Context Manager Usage

```python
async with FundamentalsClient() as fx:
    report = await fx.get_segments("SET:AOT")
```

## Enums

### `Period`

Reporting period selecting the field-id suffix on the wire.

| Member | Value | Meaning |
|--------|-------|---------|
| `Period.FY` | `"FY"` | Fiscal year (annual) |
| `Period.FQ` | `"FQ"` | Fiscal quarter |
| `Period.FH` | `"FH"` | Fiscal half-year |
| `Period.TTM` | `"TTM"` | Trailing twelve months (single period) |

### `StatementType`

| Member | Value |
|--------|-------|
| `StatementType.INCOME` | `"income"` |
| `StatementType.BALANCE` | `"balance"` |
| `StatementType.CASH_FLOW` | `"cash_flow"` |
| `StatementType.STATISTICS` | `"statistics"` |

## Methods

### `get_segments()`

```python
async def get_segments(self, symbol: str) -> SegmentReport
```

Returns revenue broken down by business source and by geography (annual).

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | `str` | — | `EXCHANGE:TICKER`; dash notation is normalized. |

#### Returns

`SegmentReport` — by-business and by-region series, newest-first.

#### Raises

| Exception | When |
|-----------|------|
| `NoFundamentalDataError` | The symbol returns no fundamentals. |
| `FundamentalsConnectionError` | The WebSocket fails or drops. |
| `FundamentalsTimeoutError` | The snapshot does not complete before `timeout`. |

#### Example

```python
async with FundamentalsClient() as fx:
    report = await fx.get_segments("SET:AOT")
    latest = report.by_business[0]
    for seg in latest.segments:
        print(latest.period.label, seg.label, seg.value)
```

### `get_income_statement()`

```python
async def get_income_statement(
    self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
) -> FinancialStatement
```

Returns the income statement. `max_periods` trims to the most recent N periods.

#### Returns

`FinancialStatement` — rows in display order, values aligned to `periods`.

### `get_balance_sheet()`

```python
async def get_balance_sheet(
    self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
) -> FinancialStatement
```

Returns the balance sheet.

### `get_cash_flow()`

```python
async def get_cash_flow(
    self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
) -> FinancialStatement
```

Returns the cash-flow statement.

### `get_statistics()`

```python
async def get_statistics(
    self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
) -> FinancialStatement
```

Returns statistics and valuation ratios.

### `get_dividends()`

```python
async def get_dividends(self, symbol: str) -> DividendReport
```

Returns dividend history and summary metrics.

### `get_earnings()`

```python
async def get_earnings(
    self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
) -> EarningsReport
```

Returns earnings: reported vs estimate and surprise, per period.

#### Raises

| Exception | When |
|-----------|------|
| `ValueError` | `period` is not `Period.FY` or `Period.FQ`. |

### `get_financials()`

```python
async def get_financials(
    self, symbol: str, period: Period = Period.FY, max_periods: int | None = None
) -> FundamentalsSnapshot
```

Returns income, balance, cash-flow, statistics, segments, dividends, and earnings in a single WebSocket round-trip. Earnings is `None` when `period` is `Period.TTM`.

#### Example

```python
async with FundamentalsClient() as fx:
    snapshot = await fx.get_financials("NASDAQ:AAPL")
    print(snapshot.currency, snapshot.income.line("total_revenue").values[:3])
```

## Exceptions

| Exception | Base | Raised when |
|-----------|------|-------------|
| `FundamentalsError` | `Exception` | Base for all fundamentals errors. |
| `FundamentalsAuthError` | `FundamentalsError` | The server rejects the auth token. |
| `FundamentalsConnectionError` | `FundamentalsError` | The WebSocket connection fails or drops. |
| `FundamentalsTimeoutError` | `FundamentalsError` | A symbol does not complete before the deadline. |
| `NoFundamentalDataError` | `FundamentalsError` | The server returns no fields (invalid symbol / no statements). |

## See Also

- [Models](models.md) — the returned Pydantic models
- [Fundamentals Guide](../../guides/fundamentals.md)
- [Financial Statements Concept](../../concepts/financial-statements.md)
