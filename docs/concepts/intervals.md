# Intervals

[Home](../index.md) > Concepts > Intervals

All tvkit APIs expect intervals in TradingView format. This format differs from most other libraries — strings like `"1h"` or `"daily"` are not accepted.

## Supported Formats

| Unit | Format | Valid Values | Examples |
|------|--------|-------------|---------|
| Seconds | `<n>S` | 1, 5, 15, 30 | `"1S"`, `"5S"`, `"15S"`, `"30S"` |
| Minutes | integer string | 1, 5, 15, 30, 60, 120, 240 | `"1"`, `"5"`, `"60"`, `"240"` |
| Days | `<n>D` | 1 (tvkit supports `1D` only) | `"1D"` |
| Weeks | `<n>W` | 1 | `"1W"` |
| Months | `<n>M` | 1, 3, 6, 12 | `"1M"`, `"3M"`, `"12M"` (12M = yearly) |

**Hours are expressed as integer minutes.** There is no `"1H"` format. Use `"60"` for 1 hour, `"240"` for 4 hours.

## Common Interval Reference

| Timeframe | Interval String |
|-----------|----------------|
| 1 second | `"1S"` |
| 5 seconds | `"5S"` |
| 1 minute | `"1"` |
| 5 minutes | `"5"` |
| 15 minutes | `"15"` |
| 30 minutes | `"30"` |
| 1 hour | `"60"` |
| 2 hours | `"120"` |
| 4 hours | `"240"` |
| Daily | `"1D"` |
| Weekly | `"1W"` |
| Monthly | `"1M"` |
| Quarterly | `"3M"` |
| Yearly | `"12M"` |

## Invalid Format Examples

These strings are rejected before any network request is made:

| Invalid | Correct |
|---------|---------|
| `"1h"` | `"60"` |
| `"4h"` | `"240"` |
| `"1d"` | `"1D"` |
| `"daily"` | `"1D"` |
| `"1w"` | `"1W"` |
| `"monthly"` | `"1M"` |
| `"yearly"` | `"12M"` |

## Choosing an Interval

Smaller intervals return more bars per day, which affects how many days of history you can fetch before hitting `MAX_BARS_REQUEST` (the per-request bar limit).

| Interval | Approximate bars per trading day |
|----------|----------------------------------|
| `"1S"` | ~86,400 |
| `"1"` | ~1,440 |
| `"5"` | ~288 |
| `"60"` | ~24 |
| `"1D"` | 1 |

Use larger intervals when requesting long historical ranges to avoid hitting bar limits. For second-level data over a full day, you may need to fetch in segments.

See [Historical Data guide](../guides/historical-data.md) for `MAX_BARS_REQUEST` details and date-range mode.

## Market Limitations

Not all markets support every interval. General guidelines:

- **Equity markets** typically support minute-level data as the smallest interval. Second-level data is rarely available for stocks.
- **Crypto markets** (Binance, Coinbase) often support second-level intervals.
- **Macro indicators** (INDEX:NDFI, USI:PCC) are available on daily intervals only.

If a requested interval is unsupported for a given symbol, TradingView returns no bars rather than an error.

## Validation

`validate_interval()` is a **synchronous** helper — no `await` needed. All tvkit async methods call it internally before opening a WebSocket connection.

```python
from tvkit.api.chart.utils import validate_interval

validate_interval("1D")   # passes silently
validate_interval("1h")   # raises ValueError: invalid interval
```

An invalid interval is always a local programming error, not a network issue.

## See Also

- [Symbols](symbols.md) — the exchange:ticker format used alongside intervals
- [Historical Data guide](../guides/historical-data.md) — count mode and date-range mode
- [Real-time Streaming guide](../guides/realtime-streaming.md) — choosing an interval for live data
