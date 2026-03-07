# Limitations

This page documents known constraints of tvkit and the underlying TradingView data API. Understanding these limits before starting a project prevents unexpected results.

## Bar Count Limit per Request

TradingView caps the number of bars returned in a single request. This cap is exposed as `MAX_BARS_REQUEST` in `tvkit.api.chart.utils`.

- The exact limit depends on your TradingView account tier.
- Free accounts receive fewer historical bars than paid accounts.
- To fetch more bars than the limit, use `get_historical_ohlcv()` in **date-range mode** and fetch in segments.
- This limit may change if TradingView updates its backend behaviour.

```python
from tvkit.api.chart.utils import MAX_BARS_REQUEST
print(MAX_BARS_REQUEST)  # inspect the current limit
```

See [Historical Data guide](guides/historical-data.md) for a segmented fetch example.

## Rate Limiting

TradingView does not publish official rate limit figures. The values below are empirical observations and may change:

- Scanner requests: allow 1–2 seconds between scans of different markets
- Simultaneous WebSocket connections: limit to a small number per IP
- Reconnection attempts: use exponential backoff to avoid triggering rate limits

## Delayed vs Real-time Data

TradingView delivers data in two modes depending on your account:

| Data Type | Free Account | Paid Account |
|-----------|-------------|-------------|
| US equities | 15-minute delay | Real-time |
| Most international equities | 15-minute delay | Real-time or exchange-dependent delay |
| Crypto | Real-time | Real-time |
| Forex | Real-time | Real-time |
| Macro indicators | End-of-day (daily updates) | End-of-day (daily updates) |

tvkit has no way to detect whether data is delayed or real-time — this depends entirely on your TradingView account configuration.

## No Futures or Options Data

tvkit currently supports equities, crypto, forex, and indices. Futures contracts and options chains are not currently supported. Options flow data is not available through this API.

## Symbol Availability Gaps

Not every symbol visible on TradingView is accessible via the API:

- Some exchanges restrict data access to paid tiers
- Certain OTC or pink-sheet instruments may be unavailable
- Delisted symbols typically return no data without an explicit error

If a symbol returns no bars, verify it exists and is accessible in TradingView's web interface using your account tier.

## Macro Indicators — Daily Only

`INDEX:NDFI`, `USI:PCC`, and similar macro indicators are published on a daily basis. Requesting intraday intervals for these symbols typically returns no data rather than an error.

## No Order Placement

tvkit is a **read-only** data library. It does not provide any trading, order placement, or portfolio management functionality. All data flows are one-way: TradingView → tvkit → your application.

## No WebSocket Multiplexing per OHLCV Stream

Each `OHLCV` context manager handles a single symbol stream. For monitoring multiple symbols simultaneously with trade-level updates, use `get_latest_trade_info()` which accepts a list of symbols in one connection.

## asyncio Required

tvkit requires an `asyncio` event loop. It is not compatible with synchronous codebases or frameworks that do not support `asyncio` (e.g., some legacy WSGI applications). See [Why tvkit?](why-tvkit.md#when-not-to-use-tvkit) for more detail.

## Data Reliability

TradingView aggregates data from multiple exchange feeds and providers. In rare cases, bars may differ slightly from exchange-native feeds or other data vendors due to this aggregation.

tvkit does not modify or normalize TradingView data beyond structural parsing into typed `OHLCV` objects. What TradingView returns is what tvkit delivers.

## See Also

- [Why tvkit?](why-tvkit.md) — design goals and scope
- [Data Sources](data-sources.md) — data origin and quality notes
- [FAQ](faq.md) — common questions about limitations
