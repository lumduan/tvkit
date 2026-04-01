# Account Capabilities

**Available since:** v0.7.0

tvkit can authenticate with a TradingView user account to unlock deeper historical data and higher bar limits. This page explains how account tiers map to data limits, how tvkit detects those limits automatically, and how to use this information when fetching data.

---

## TradingView Plans and Bar Limits

TradingView offers five plan levels. Each plan determines the maximum number of bars accessible in a single historical fetch. See the [official TradingView pricing page](https://www.tradingview.com/pricing/) for the full feature comparison.

| TradingView plan | Internal plan slug | tvkit `tier` | `max_bars` |
|------------------|--------------------|--------------|------------|
| Basic (free) | *(none)* | `free` | 5,000 |
| Essential | `pro` | `pro` | 10,000 |
| Plus | `pro_plus` | `pro` | 10,000 |
| Premium | `pro_premium` | `premium` | 20,000 |
| Ultimate | `ultimate` | `ultimate` | 40,000 |

> **Note:** These limits are empirical. tvkit's background probe confirms the actual server-enforced limit for your session; the figures above are starting estimates only.

The **internal plan slug** is the raw `pro_plan` value in TradingView's user profile. The **tvkit `tier`** is the normalized label exposed via `account.tier`. For example, both the Essential (`pro`) and Plus (`pro_plus`) plan slugs normalize to `account.tier == "pro"`.

---

## How tvkit Detects Capabilities

Capability detection runs in two stages after authentication.

### Stage 1 — Plan-based estimate (immediate)

As soon as `__aenter__` completes, tvkit reads the `pro_plan` field from the TradingView homepage bootstrap payload and maps it to `max_bars` using the table above.

This estimate is available immediately via `client.account.max_bars`. It is a best-effort value — sufficient for most use cases.

### Stage 2 — Background WebSocket probe (async)

In parallel, tvkit launches a background task that opens a short-lived dedicated WebSocket connection and requests a large number of daily bars. The number of bars the server actually returns reveals the true server-enforced limit.

When the probe completes:

- `account.max_bars` is updated to the confirmed value
- `account.probe_confirmed` is set to `True`
- `account.max_bars_source` changes from `"estimate"` to `"probe"`
- `account.probe_status` changes from `"pending"` to `"success"`

The probe uses a **dedicated short-lived connection** — it never interferes with any active OHLCV stream.

### Probe resilience

To handle regional restrictions, delistings, or server-side throttling, the probe uses fallback strategies:

- **Symbol fallback chain:** `NASDAQ:AAPL` → `BINANCE:BTCUSDT` → `INDEX:SPX`
- **Adaptive bars_count:** `50,000` → `40,000` → `20,000` — tried in order on throttle or disconnect

If all attempts are exhausted, the plan-based estimate is retained and `probe_status` is set to `"throttled"` or `"failed"`.

---

## `max_bars_source`

The `account.max_bars_source` field tells you where the current `max_bars` value came from:

| Value | Meaning |
|-------|---------|
| `"estimate"` | Plan-based lookup — immediately available; may not reflect the actual server limit |
| `"probe"` | Live WebSocket probe confirmed the value — most accurate |

For most historical fetch workloads, the plan estimate is accurate enough. For maximum precision when requesting very large bar counts, wait for the probe to confirm.

---

## `probe_status` Lifecycle

```
pending → success
       → throttled
       → failed
```

| Status | Meaning |
|--------|---------|
| `pending` | Probe not yet started or still in progress |
| `success` | Probe confirmed `max_bars`; `max_bars_source` is `"probe"` |
| `throttled` | All probe bars_count attempts were rate-limited; estimate retained |
| `failed` | All symbol + bars combinations exhausted; estimate retained |

`throttled` and `failed` are non-fatal — the session continues with the plan estimate.

---

## Premium WebSocket Endpoint

For authenticated accounts on a paid tier (`essential`, `pro`, `premium`, `ultimate`), tvkit automatically connects to `prodata.tradingview.com` instead of the standard `data.tradingview.com`. This endpoint delivers the full `max_bars` for your account in a single large message batch rather than requiring multiple paginated requests.

| Session mode | WebSocket endpoint | Max bars per fetch |
| --- | --- | --- |
| Anonymous / free | `data.tradingview.com` | 5,000 |
| Paid tier (browser / cookie-dict) | `prodata.tradingview.com` | Plan `max_bars` (10k–40k) |
| Direct token (`auth_token=...`) | `data.tradingview.com` | 5,000 — no plan info available |

> **Direct token limitation:** `auth_token=...` mode skips the profile fetch, so `account` is `None` and the tier is unknown. tvkit cannot switch to `prodata.tradingview.com` without a confirmed tier. Use browser or cookie-dict mode to benefit from the premium endpoint.

---

## `wait_until_ready()`

Call `wait_until_ready()` to block until the background probe finishes before issuing the first historical fetch:

```python
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV(browser="chrome") as client:
    await client.wait_until_ready()  # waits for probe to confirm max_bars
    bars = await client.get_historical_ohlcv(
        exchange_symbol="NASDAQ:AAPL",
        interval="1",
        bars_count=100_000,
    )
```

**When to use it:**

- You need the highest possible accuracy for `max_bars` before fetching
- You are requesting very large bar counts near the account limit
- You want `account.probe_status == "success"` guaranteed before proceeding

**When to skip it:**

- You are streaming real-time data (`get_ohlcv()`, `get_quote_data()`) — no bar limit applies
- You are fetching moderate bar counts (well within the free-tier limit of 5,000)
- Fast startup time is more important than probe-confirmed accuracy

**Trade-off:** `wait_until_ready()` adds startup latency equal to the probe duration (typically a few seconds depending on network conditions). For most applications, the plan-based estimate is accurate enough to proceed immediately.

**Probe failures are non-fatal:** If the probe fails or is cancelled, `wait_until_ready()` returns silently and the plan estimate remains in effect.

---

## Probe Result Cache

To avoid re-probing every session start, tvkit maintains an on-disk probe result cache at:

```
~/.cache/tvkit/capabilities.json
```

The cache is keyed by TradingView `user_id`. If a cached result is younger than 24 hours, the live probe is skipped and the cached `max_bars` is used directly. The cache is invalidated automatically when the TTL expires.

---

## 2FA Transparency

tvkit inherits the browser's already-authenticated session. Since the browser has already handled two-factor authentication, tvkit requires no additional 2FA steps. If the browser session requires re-authentication (e.g., session expired), a `BrowserCookieError` is raised — log in again in Chrome or Firefox and re-enter the `OHLCV` context manager.

---

## Checking Capabilities at Runtime

```python
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV(browser="chrome") as client:
    account = client.account
    if account is not None:
        print(f"TradingView plan: {account.plan!r}")
        print(f"Tier: {account.tier}")
        print(f"Max bars: {account.max_bars} (source: {account.max_bars_source})")
        print(f"Probe status: {account.probe_status}")
```

`client.account` returns `None` for:

- **Anonymous sessions** — no credentials provided; operates with 5,000-bar free-tier limits
- **Direct token sessions** (`auth_token=...`) — no profile fetch is performed; plan information is not available in this mode

---

## See Also

- [Authenticated Sessions Guide](../guides/authenticated-sessions.md)
- [Authentication Reference — `tvkit.auth`](../reference/auth/index.md)
- [TradingViewCredentials Reference](../reference/auth/credentials.md)
- [TradingViewAccount Reference](../reference/auth/account.md)
- [OHLCV Client Reference](../reference/chart/ohlcv.md)
- [Limitations — Authentication Limitations](../limitations.md#authentication-limitations)
- [TradingView Pricing](https://www.tradingview.com/pricing/)
