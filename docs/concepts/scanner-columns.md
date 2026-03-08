# Scanner Column Sets

[Home](../index.md) > Concepts > Scanner Column Sets

The scanner API exposes **over 100 financial columns** per stock. To avoid fetching unnecessary data, tvkit provides predefined **column sets** that group related metrics together. Column sets can also be combined if you need metrics from multiple categories.

## Available Column Sets

| Column Set | Example Fields | When to Use |
|------------|---------------|-------------|
| `BASIC` | Price, change, volume, market cap, 52-week high/low | Quick price screening or dashboards |
| `FUNDAMENTALS` | EPS, revenue, P/E, P/B, dividends, EV/Revenue, PEG | Fundamental analysis |
| `TECHNICAL_INDICATORS` | RSI, MACD, Stochastic, CCI, momentum, recommendations | Technical screening |
| `PERFORMANCE` | YTD, 1M, 3M, 6M, 1Y, 5Y, 10Y returns, volatility | Return and risk comparisons |
| `VALUATION` | P/E, P/B, P/S, EV/EBITDA, EV/Revenue, PEG ratio | Valuation screening |
| `PROFITABILITY` | ROE, ROA, gross margin, operating margin, net margin, EBITDA | Profitability screening |
| `FINANCIAL_STRENGTH` | Debt/equity, current ratio, quick ratio, free cash flow | Balance sheet health |
| `CASH_FLOW` | Operating, investing, financing cash flows, FCF margin | Cash flow analysis |
| `DIVIDENDS` | Yield, payout ratio, growth rate, continuous growth years | Dividend screening |
| `COMPREHENSIVE_FULL` | All 100+ columns | Full data extraction — use sparingly |

## Category Reference

| Category | Included In |
|----------|------------|
| Price data | `BASIC`, `TECHNICAL_INDICATORS` |
| Valuation ratios | `VALUATION`, `FUNDAMENTALS` |
| Profitability | `PROFITABILITY`, `COMPREHENSIVE_FULL` |
| Financial health | `FINANCIAL_STRENGTH`, `COMPREHENSIVE_FULL` |
| Dividends | `DIVIDENDS`, `FUNDAMENTALS` |
| Performance returns | `PERFORMANCE`, `COMPREHENSIVE_FULL` |
| Technical indicators | `TECHNICAL_INDICATORS` |
| Cash flow | `CASH_FLOW`, `COMPREHENSIVE_FULL` |

## Choosing a Column Set

- Use `BASIC` when you only need price, volume, or market cap — it is the fastest response.
- Use `FUNDAMENTALS` or `VALUATION` for stock screening based on financial ratios.
- Use `TECHNICAL_INDICATORS` for momentum or mean-reversion strategies.
- Avoid `COMPREHENSIVE_FULL` for frequent or large scans — it fetches all 100+ columns and significantly increases response time.
- Column sets can be combined: pass multiple sets to retrieve metrics from different categories in one request.

## Performance Considerations

Each additional column increases the payload size returned by the scanner. For large scans (many markets or many symbols per market):

- Prefer smaller column sets like `BASIC`
- Avoid `COMPREHENSIVE_FULL` unless you truly need all fields
- Fetch additional metrics in a second, filtered pass rather than pulling all columns upfront

## Usage

```python
from tvkit.api.scanner import ScannerService, Market
from tvkit.api.scanner import create_comprehensive_request
from tvkit.api.scanner.models.scanner import ColumnSets

service = ScannerService()

request = create_comprehensive_request(
    sort_by="market_cap_basic",
    sort_order="desc",
    range_end=20,
)

response = await service.scan_market(Market.US, request)
```

See the [Scanner guide](../guides/scanner.md) for full request construction and filtering examples.

## Inspecting Available Columns

For the complete list of available scanner fields including exact column names, data types, and descriptions, see:

- [Scanner API reference](../reference/scanner/scanner.md)

## See Also

- [Scanner guide](../guides/scanner.md) — building requests, applying filters, regional scanning
- [Scanner API reference](../reference/scanner/scanner.md) — full column list and field names
