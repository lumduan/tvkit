# Scanner Reference

**Module:** `tvkit.api.scanner`
**Available since:** v0.2.0

Async HTTP client for TradingView's market screener API. Supports 69 global markets with 101+ financial columns, exponential-backoff retry logic, and Pydantic response validation.

## Quick Example

```python
import asyncio
from tvkit.api.scanner.markets import Market
from tvkit.api.scanner.models import create_scanner_request
from tvkit.api.scanner.services import ScannerService

async def main() -> None:
    request = create_scanner_request(range_end=10)  # uses ColumnSets.DETAILED by default
    async with ScannerService() as service:
        result = await service.scan_market(Market.AMERICA, request)
    for stock in result.data:
        print(f"{stock.name}: {stock.close} {stock.currency}")

asyncio.run(main())
```

---

## Import

```python
from tvkit.api.scanner.services import ScannerService, create_comprehensive_request
from tvkit.api.scanner.services.scanner_service import (
    ScannerServiceError,
    ScannerConnectionError,
    ScannerAPIError,
    ScannerValidationError,
)
from tvkit.api.scanner.models import (
    ColumnSets,
    ScannerRequest,
    ScannerResponse,
    ScannerOptions,
    SortConfig,
    StockData,
    create_scanner_request,
)
from tvkit.api.scanner.markets import Market
```

---

## `ScannerService`

Async context manager that makes POST requests to `scanner.tradingview.com` with exponential-backoff retry logic.

### Signature

```python
class ScannerService:
    def __init__(
        self,
        base_url: str = "https://scanner.tradingview.com",
        timeout: float = 30.0,
        max_retries: int = 3,
        user_agent: str = "tvkit/1.0",
    ) -> None: ...
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | `"https://scanner.tradingview.com"` | Base URL for the scanner API. |
| `timeout` | `float` | `30.0` | Request timeout in seconds. |
| `max_retries` | `int` | `3` | Maximum retry attempts on connection errors. |
| `user_agent` | `str` | `"tvkit/1.0"` | User-Agent header sent with all requests. |

### Context Manager Usage

```python
async with ScannerService() as service:
    response = await service.scan_market(Market.AMERICA, request)
```

---

## Methods

### `scan_market()`

Scan a specific market by `Market` enum value.

> **Which method to use?** Use `scan_market()` when you have a known market at write time — pass a `Market` enum member directly. Use `scan_market_by_id()` when the market identifier is determined at runtime (e.g., read from config or user input).

```python
async def scan_market(
    self,
    market: Market,
    request: ScannerRequest,
    label_product: str = "markets-screener",
) -> ScannerResponse: ...
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `market` | `Market` | required | Market to scan. Use `Market` enum values. |
| `request` | `ScannerRequest` | required | Scanner request configuration. |
| `label_product` | `str` | `"markets-screener"` | Label product parameter sent to the API. |

**Returns:** `ScannerResponse` — Parsed response containing matching stocks.

**Raises:**

| Exception | When |
|-----------|------|
| `ScannerConnectionError` | Connection fails after all retries |
| `ScannerAPIError` | API returns a non-200 status code |
| `ScannerValidationError` | Response fails Pydantic validation |
| `ValueError` | Market is invalid |

**Retry behaviour:** On `ScannerConnectionError`, the service retries up to `max_retries` times with exponential backoff. `ScannerAPIError` and `ScannerValidationError` are not retried.

| Attempt | Wait before retry |
|---------|-------------------|
| 1 (initial) | — |
| 2 | 1 s (`2.0 ** 0`) |
| 3 | 2 s (`2.0 ** 1`) |
| 4 (final) | 4 s (`2.0 ** 2`) |

**Example:**

```python
from tvkit.api.scanner.markets import Market
from tvkit.api.scanner.models import ColumnSets, create_scanner_request
from tvkit.api.scanner.services import ScannerService

request = create_scanner_request(
    columns=ColumnSets.BASIC,
    sort_by="market_cap_basic",
    sort_order="desc",
    range_end=50,
)

async with ScannerService() as service:
    response = await service.scan_market(Market.AMERICA, request)

print(f"Found {len(response.data)} stocks")
for stock in response.data:
    print(f"{stock.name}: {stock.close} {stock.currency}")
```

---

### `scan_market_by_id()`

Scan a market by its string identifier instead of `Market` enum. Internally validates the string and delegates to `scan_market()`.

```python
async def scan_market_by_id(
    self,
    market_id: str,
    request: ScannerRequest,
    label_product: str = "markets-screener",
) -> ScannerResponse: ...
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `market_id` | `str` | required | Market identifier string (e.g., `"america"`, `"thailand"`, `"japan"`). |
| `request` | `ScannerRequest` | required | Scanner request configuration. |
| `label_product` | `str` | `"markets-screener"` | Label product parameter. |

**Returns:** `ScannerResponse`

**Raises:**

| Exception | When |
|-----------|------|
| `ValueError` | `market_id` is not a valid market identifier |
| `ScannerConnectionError` | Connection fails after all retries |
| `ScannerAPIError` | API returns non-200 status |
| `ScannerValidationError` | Response validation fails |

**Example:**

```python
async with ScannerService() as service:
    response = await service.scan_market_by_id("thailand", request)
```

---

## Factory Functions

### `create_scanner_request()`

Create a `ScannerRequest` with sensible defaults.

```python
def create_scanner_request(
    columns: list[str] | None = None,
    preset: str = "all_stocks",
    sort_by: str = "name",
    sort_order: Literal["asc", "desc"] = "asc",
    range_start: int = 0,
    range_end: int = 1000,
    language: str = "en",
) -> ScannerRequest: ...
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `columns` | `list[str] \| None` | `None` | Columns to request. Defaults to `ColumnSets.DETAILED` when `None`. |
| `preset` | `str` | `"all_stocks"` | Scanner preset. |
| `sort_by` | `str` | `"name"` | Field to sort results by. |
| `sort_order` | `"asc" \| "desc"` | `"asc"` | Sort direction. |
| `range_start` | `int` | `0` | Start index for results (0-based). |
| `range_end` | `int` | `1000` | End index for results (exclusive). Maximum 10,000 items per request. |
| `language` | `str` | `"en"` | Language code for response localization (must be 2 characters). |

**Returns:** `ScannerRequest`

**Example:**

```python
from tvkit.api.scanner.models import ColumnSets, create_scanner_request

request = create_scanner_request(
    columns=ColumnSets.VALUATION,
    sort_by="price_earnings_ttm",
    sort_order="asc",
    range_end=100,
)
```

---

### `create_comprehensive_request()`

Create a `ScannerRequest` using `ColumnSets.COMPREHENSIVE_FULL` — all available TradingView scanner columns.

```python
def create_comprehensive_request(
    sort_by: str = "name",
    sort_order: Literal["asc", "desc"] = "asc",
    range_start: int = 0,
    range_end: int = 1000,
    language: str = "en",
) -> ScannerRequest: ...
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sort_by` | `str` | `"name"` | Field to sort results by. |
| `sort_order` | `"asc" \| "desc"` | `"asc"` | Sort direction. |
| `range_start` | `int` | `0` | Start index (0-based). |
| `range_end` | `int` | `1000` | End index (exclusive). |
| `language` | `str` | `"en"` | Language code. |

**Returns:** `ScannerRequest` with `columns=ColumnSets.COMPREHENSIVE_FULL`.

**Example:**

```python
from tvkit.api.scanner.services import ScannerService, create_comprehensive_request
from tvkit.api.scanner.markets import Market

request = create_comprehensive_request(
    sort_by="market_cap_basic",
    sort_order="desc",
    range_end=50,
)

async with ScannerService() as service:
    response = await service.scan_market(Market.AMERICA, request)
```

---

## Column Sets

Predefined lists of TradingView scanner column names. Use as the `columns` argument to `create_scanner_request()`.

```python
from tvkit.api.scanner.models import ColumnSets
```

| Set Name | Column Count | Best For |
|----------|-------------|----------|
| `ColumnSets.BASIC` | 5 | Quick price and volume overview |
| `ColumnSets.DETAILED` | 20 | General screening (default) |
| `ColumnSets.FUNDAMENTALS` | 9 | Earnings, valuation, dividend summary |
| `ColumnSets.TECHNICAL` | 9 | OHLCV and relative volume |
| `ColumnSets.PERFORMANCE` | 14 | Return periods and volatility |
| `ColumnSets.VALUATION` | 10 | P/E, P/S, P/B, EV ratios |
| `ColumnSets.DIVIDENDS` | 9 | Yield, payout ratio, DPS history |
| `ColumnSets.PROFITABILITY` | 9 | Margins and return on capital |
| `ColumnSets.FINANCIAL_STRENGTH` | 9 | Debt, cash, liquidity ratios |
| `ColumnSets.CASH_FLOW` | 7 | Operating, free, and capex cash flows |
| `ColumnSets.TECHNICAL_INDICATORS` | 13 | RSI, MACD, Stochastic, Momentum |
| `ColumnSets.COMPREHENSIVE` | 20 | Mixed key metrics across categories |
| `ColumnSets.COMPREHENSIVE_FULL` | ~90+ (varies) | All available scanner columns |

**Column set column lists:**

`BASIC`: `name`, `close`, `currency`, `change`, `volume`

`DETAILED`: `name`, `close`, `pricescale`, `minmov`, `fractional`, `minmove2`, `currency`, `change`, `volume`, `relative_volume_10d_calc`, `market_cap_basic`, `fundamental_currency_code`, `price_earnings_ttm`, `earnings_per_share_diluted_ttm`, `earnings_per_share_diluted_yoy_growth_ttm`, `dividends_yield_current`, `sector.tr`, `market`, `sector`, `recommendation_mark`

`FUNDAMENTALS`: `name`, `close`, `currency`, `market_cap_basic`, `price_earnings_ttm`, `earnings_per_share_diluted_ttm`, `dividends_yield_current`, `sector`, `recommendation_mark`

`TECHNICAL`: `name`, `close`, `currency`, `change`, `volume`, `relative_volume_10d_calc`, `high`, `low`, `open`

`PERFORMANCE`: `name`, `close`, `currency`, `Perf.W`, `Perf.1M`, `Perf.3M`, `Perf.6M`, `Perf.YTD`, `Perf.Y`, `Perf.5Y`, `Perf.10Y`, `Perf.All`, `Volatility.W`, `Volatility.M`

`VALUATION`: `name`, `close`, `currency`, `market_cap_basic`, `price_earnings_ttm`, `price_earnings_growth_ttm`, `price_sales_current`, `price_book_fq`, `enterprise_value_current`, `enterprise_value_to_revenue_ttm`

`DIVIDENDS`: `name`, `close`, `currency`, `dividends_yield_current`, `dividends_yield`, `dividend_payout_ratio_ttm`, `dps_common_stock_prim_issue_fy`, `continuous_dividend_payout`, `continuous_dividend_growth`

`PROFITABILITY`: `name`, `close`, `currency`, `gross_margin_ttm`, `operating_margin_ttm`, `net_margin_ttm`, `return_on_assets_fq`, `return_on_equity_fq`, `return_on_invested_capital_fq`

`FINANCIAL_STRENGTH`: `name`, `close`, `currency`, `total_assets_fq`, `total_debt_fq`, `net_debt_fq`, `current_ratio_fq`, `quick_ratio_fq`, `debt_to_equity_fq`

`CASH_FLOW`: `name`, `close`, `currency`, `cash_f_operating_activities_ttm`, `free_cash_flow_ttm`, `free_cash_flow_margin_ttm`, `capital_expenditures_ttm`

`TECHNICAL_INDICATORS`: `name`, `close`, `currency`, `RSI`, `Mom`, `AO`, `CCI20`, `Stoch.K`, `Stoch.D`, `MACD.macd`, `MACD.signal`, `Recommend.All`, `Recommend.MA`

`COMPREHENSIVE`: `name`, `description`, `close`, `currency`, `change`, `volume`, `market_cap_basic`, `price_earnings_ttm`, `earnings_per_share_diluted_ttm`, `dividends_yield_current`, `sector`, `market`, `recommendation_mark`, `Perf.YTD`, `Perf.Y`, `gross_margin_ttm`, `return_on_equity_fq`, `free_cash_flow_ttm`, `debt_to_equity_fq`, `RSI`

For the full column list of `COMPREHENSIVE_FULL` (approximately 90 columns; may vary as TradingView adds or removes fields), see [concepts/scanner-columns.md](../../concepts/scanner-columns.md).

---

## Type Definitions

### `ScannerRequest`

```python
from tvkit.api.scanner.models import ScannerRequest
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `columns` | `list[str]` | required | Column names to retrieve |
| `ignore_unknown_fields` | `bool` | `False` | When `True`, unknown column names returned by TradingView are silently ignored instead of raising a validation error. Set to `True` when using `COMPREHENSIVE_FULL` against markets that may return additional fields. |
| `options` | `ScannerOptions` | `ScannerOptions()` | Language and other options |
| `range` | `tuple[int, int]` | required | `(start, end)` result range. `end - start` must not exceed 10,000 |
| `sort` | `SortConfig` | required | Sort configuration |
| `preset` | `str` | required | Scanner preset (e.g., `"all_stocks"`) |

### `ScannerResponse`

```python
from tvkit.api.scanner.models import ScannerResponse
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `data` | `list[StockData]` | required | List of matched stocks |
| `total_count` | `int \| None` | `None` | Total number of results available in the market (use for pagination math). Populated from the `totalCount` field in the TradingView response. |
| `next_page_token` | `str \| None` | `None` | Reserved; mapped from `nextPageToken` in the API response. TradingView does not currently return this field — use `range_start` / `range_end` for pagination instead (see [Pagination](#pagination)). |

### `StockData`

```python
from tvkit.api.scanner.models import StockData
```

Represents one row from the TradingView scanner response. Fields correspond to TradingView column names — for example, `RSI`, `Perf.Y`, and `MACD.macd` are TradingView-defined identifiers requested via `ColumnSets`. Fields beyond `name` are `None` when the corresponding column was not included in the request.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Stock ticker symbol |
| `close` | `float \| None` | Last close price |
| `currency` | `str \| None` | Currency code |
| `change` | `float \| None` | Price change |
| `volume` | `int \| None` | Trading volume |
| `market_cap_basic` | `int \| None` | Market capitalisation |
| `price_earnings_ttm` | `float \| None` | P/E ratio (TTM) |
| `dividends_yield_current` | `float \| None` | Current dividend yield |
| `sector` | `str \| None` | Sector classification |
| `recommendation_mark` | `float \| None` | Analyst recommendation score |

Additional fields are accepted via `extra = "allow"` — any column in `ColumnSets.COMPREHENSIVE_FULL` is accessible.

### `SortConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sort_by` | `str` | required | Field name to sort by |
| `sort_order` | `"asc" \| "desc"` | `"asc"` | Sort direction |
| `nulls_first` | `bool` | `False` | Whether nulls appear first |

### `ScannerOptions`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lang` | `str` | `"en"` | Language code (must be 2 characters) |

---

## Supported Markets

`ScannerService` supports 69 global markets across 6 regions. These correspond to TradingView's public market identifiers — each value maps directly to a scanner endpoint path on `scanner.tradingview.com`. Pass any `Market` enum member to `scan_market()`.

```python
from tvkit.api.scanner.markets import Market

# Examples
Market.AMERICA      # US equities (NYSE, NASDAQ, AMEX)
Market.CANADA       # Toronto Stock Exchange
Market.JAPAN        # Tokyo Stock Exchange
Market.THAILAND     # Stock Exchange of Thailand
Market.GERMANY      # Frankfurt Stock Exchange
Market.INDIA        # NSE / BSE
```

For the full list of 69 markets with exchange details and regional groupings, see the [Markets Reference](markets.md).

---

## Pagination

The TradingView scanner API is page-based via `range_start` and `range_end`. There is no cursor token — increment the range to fetch the next page.

```python
import asyncio
from tvkit.api.scanner.markets import Market
from tvkit.api.scanner.models import StockData, create_scanner_request
from tvkit.api.scanner.services import ScannerService

async def fetch_all(market: Market) -> list[StockData]:
    all_stocks: list[StockData] = []
    start: int = 0
    step: int = 100

    async with ScannerService() as service:
        while True:
            request = create_scanner_request(
                range_start=start,
                range_end=start + step,
            )
            result = await service.scan_market(market, request)
            all_stocks.extend(result.data)
            if len(result.data) < step:
                break  # last page
            start += step

    return all_stocks

asyncio.run(fetch_all(Market.AMERICA))
```

> **Tip:** `result.total_count` gives the total number of matching stocks. You can use it to calculate the number of pages up front:
>
> ```python
> import math
> pages = math.ceil(result.total_count / step)
> ```

---

## Limits

| Limit | Value |
|-------|-------|
| Maximum rows per request | 10,000 (`range_end - range_start`) |
| Default rows per request | 1,000 (factory function default) |
| Request timeout | 30 s (configurable via `ScannerService(timeout=...)`) |
| Retry attempts | 3 (configurable via `ScannerService(max_retries=...)`) |
| Language code | 2-character ISO 639-1 (e.g., `"en"`, `"ja"`) |

**Additional behaviour notes:**

- Large column sets (e.g., `COMPREHENSIVE_FULL`) increase response payload size and may increase latency.
- TradingView may throttle requests silently. If you receive repeated `ScannerConnectionError`, add a short `asyncio.sleep()` between pages.
- Column availability varies by market — some markets do not populate all columns in `COMPREHENSIVE_FULL`. Missing values are returned as `None` in `StockData`.
- `COMPREHENSIVE_FULL` column count may change without notice as TradingView updates its scanner API.

---

## Exception Hierarchy

```
ScannerServiceError
├── ScannerConnectionError   — network failures, timeouts (retried)
├── ScannerAPIError          — HTTP non-200 responses (not retried)
└── ScannerValidationError   — Pydantic validation failures (not retried)
```

```python
from tvkit.api.scanner.services.scanner_service import (
    ScannerServiceError,
    ScannerConnectionError,
    ScannerAPIError,
    ScannerValidationError,
)
```

---

## See Also

- [Scanner Guide](../../guides/scanner.md)
- [Markets Reference](markets.md)
- [Exporting Guide](../../guides/exporting.md)
- [Concepts: Scanner Columns](../../concepts/scanner-columns.md)
