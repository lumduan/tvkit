# Limitations

This page documents known constraints of tvkit and the underlying TradingView data API. Understanding these limits before starting a project prevents unexpected results.

## Bar Count Limit per Request

TradingView caps the number of bars returned in a single WebSocket request. This cap is exposed as `MAX_BARS_REQUEST` in `tvkit.api.chart.utils`.

- The exact limit depends on your TradingView account tier (free tier: 5,000 bars).
- In date-range mode, `get_historical_ohlcv()` automatically segments large requests — no manual workaround needed. See [Large Date Range Fetching](guides/historical-data.md#large-date-range-fetching-automatic-segmentation).
- This limit is separate from the server-side historical depth limit described below.

```python
from tvkit.api.chart.utils import MAX_BARS_REQUEST
print(MAX_BARS_REQUEST)  # inspect the current limit
```

---

## TradingView Historical Depth Limitation

Separate from the per-request bar limit, TradingView imposes a server-side rolling window that controls how far back in time data is accessible. This window is not the number of bars per request — it is the maximum age of accessible data for your account tier.

Free/basic accounts can access approximately ≈5,000 bars backward from the current time. Paid tiers allow deeper history. The table below shows approximate accessible depth by interval and account tier:

| Interval | Basic (free) | Essential / Plus | Premium | Ultimate |
| -------- | ------------ | ---------------- | ------- | -------- |
| 1 minute | ≈3.5 days | ≈17 days | ≈1 month | ≈6 months |
| 5 minutes | ≈17 days | ≈3 months | ≈6 months | ≈2 years |
| 15 minutes | ≈52 days | ≈9 months | ≈1.5 years | ≈6 years |
| 1 hour | ≈7 months | ≈3 years | ≈6 years | ≈24 years |
| 1 day | ≈27 years | Unlimited | Unlimited | Unlimited |

These are approximate, empirical values. TradingView does not publish official figures and limits may change.

**Effect on segmented fetching:**

When `get_historical_ohlcv()` automatically segments a large date range, segments that fall before the accessible window for your account tier return no bars. tvkit treats these as empty results — no error is raised. This behavior mirrors TradingView's native chart behavior.

**Distinction from `MAX_BARS_REQUEST`:**

| Concept | What it controls |
| ------- | ---------------- |
| `MAX_BARS_REQUEST` | Protocol limit — maximum bars in a single fetch request |
| Historical depth | Server-side policy — maximum age of accessible data per account tier |

**Resolution:** To access older data, upgrade your TradingView account tier or switch to a wider interval (e.g., `"1H"` instead of `"1"`).

## Rate Limiting

TradingView does not publish official rate limit figures. The values below are empirical observations and may change:

- Scanner requests: allow 1–2 seconds between scans of different markets
- Simultaneous WebSocket connections: limit to a small number per IP
- Reconnection attempts: use exponential backoff to avoid triggering rate limits

## Delayed vs Real-time Data

TradingView delivers data in two modes depending on your account:

| Data Type | Free Account | Paid Account |
| --------- | ------------ | ------------ |
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

## Authentication Limitations

The following limitations apply when using authenticated sessions (v0.7.0+). See [Authenticated Sessions Guide](guides/authenticated-sessions.md) for usage details and [Account Capabilities](concepts/capabilities.md) for the plan-to-limit mapping.

### Browser Login Required Before Running tvkit

In browser mode, you must be logged in to TradingView in Chrome or Firefox before calling `OHLCV(browser=...)`. tvkit reads your existing browser session — it does not perform a browser-based login itself. If the session is missing or expired, `BrowserCookieError` is raised.

### Chrome and Firefox Only (v0.7.0)

Only Chrome and Firefox are supported in v0.7.0. Safari, Edge, and Brave are not supported; support may be added in a future version. As a fallback, use `cookies={...}` or `auth_token=...`.

### `browser_cookie3` Fragility

Cookie extraction can fail due to:

- Chrome or Firefox updates that change the cookie database format
- macOS Keychain access prompts being dismissed
- Browser database lock when the browser is running on some Linux setups

If browser extraction is unreliable in your environment, fall back to `cookies={...}` (inject a pre-extracted cookie dict) or `auth_token=...` (inject a direct token).

### No Automatic Token Refresh

For `auth_token=...` and `cookies={...}` modes, tvkit does not refresh the token or cookies automatically. If the token expires during a session, `AuthError` is raised. Re-enter the `OHLCV` context manager with a fresh token.

### No Token Persistence Across Sessions

tvkit never caches credentials to disk. Browser cookie extraction runs on every `OHLCV()` context manager entry. (The probe result cache stores only the confirmed `max_bars` integer, not credentials.)

### Background Probe Timing

The first historical fetch may use the plan-based `max_bars` estimate rather than the probe-confirmed value if the probe has not yet completed. Call `await client.wait_until_ready()` before the first fetch to guarantee a probe-confirmed segment size. See [Account Capabilities — wait_until_ready()](concepts/capabilities.md#wait_until_ready).

### Homepage Bootstrap Parsing Fragility

tvkit uses a 4-strategy fallback to extract the user profile from the TradingView homepage HTML. If TradingView changes its frontend structure, later strategies are tried automatically, but parsing may fail entirely and raise `ProfileFetchError`. Monitor `WARNING` log messages for strategy indices above `0` — these indicate a degraded extraction path that may break on the next TradingView frontend update.

---

## See Also

- [Why tvkit?](why-tvkit.md) — design goals and scope
- [Data Sources](data-sources.md) — data origin and quality notes
- [FAQ](faq.md) — common questions about limitations
