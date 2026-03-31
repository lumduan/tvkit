# Authentication Reference — `tvkit.auth`

**Module:** `tvkit.auth`
**Available since:** v0.7.0

The `tvkit.auth` module handles TradingView account authentication and capability detection. It is used internally by the `OHLCV` client and can also be used directly for advanced scenarios.

---

## Module Layout

| Component | File | Responsibility |
|-----------|------|----------------|
| `AuthManager` | `auth_manager.py` | Async context manager — orchestrates the full auth lifecycle |
| `TradingViewCredentials` | `credentials.py` | Credentials dataclass — browser, cookies, token, or anonymous |
| `TradingViewAccount` | `models.py` | Account profile and capability limits |
| `CookieProvider` | `cookie_provider.py` | Browser cookie extraction via `browser_cookie3` |
| `CapabilityDetector` | `capability_detector.py` | Maps plan slug → `(max_bars, tier)` |
| `TokenProvider` | `token_provider.py` | Fetches `auth_token` + profile from TradingView homepage |
| `ProfileParser` | `profile_parser.py` | 4-strategy bootstrap extraction from TradingView HTML |
| `ProbeCache` | `probe_cache.py` | Optional on-disk cache for probe results (24h TTL) |
| Exceptions | `exceptions.py` | `AuthError`, `BrowserCookieError`, `ProfileFetchError`, `CapabilityProbeError` |

---

## Public API

```python
from tvkit.auth import (
    AuthManager,
    TradingViewCredentials,
    TradingViewAccount,
    AuthError,
    BrowserCookieError,
    ProfileFetchError,
    CapabilityProbeError,
)
```

In most cases, you do not need to import `tvkit.auth` directly. Pass authentication parameters to `OHLCV()` and use `client.account` to access the result:

```python
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV(browser="chrome") as client:
    account = client.account  # TradingViewAccount | None
```

---

## Authentication Modes

`AuthManager` supports four modes determined by `TradingViewCredentials`:

| Mode | How | `account` | Probe launched |
|------|-----|-----------|----------------|
| **Anonymous** | No credentials | `None` | No |
| **Browser** | `browser="chrome"` or `"firefox"` | `TradingViewAccount` | Yes |
| **Cookie dict** | `cookies={...}` | `TradingViewAccount` | Yes |
| **Direct token** | `auth_token="..."` | `None` | No |

---

## Exception Hierarchy

```
AuthError
├── BrowserCookieError    — browser extraction failed
├── ProfileFetchError     — homepage bootstrap parse failed or session expired
└── CapabilityProbeError  — background probe failed (non-fatal by default)
```

| Exception | When raised | Recovery |
|-----------|-------------|----------|
| `BrowserCookieError` | `browser_cookie3` not installed; `sessionid` missing; browser database locked | Log in to TradingView in the browser, then retry |
| `ProfileFetchError` | Bootstrap parse failed; `user` null or empty; `auth_token` missing or too short; HTTP 5xx | Session likely expired — log in again; transient HTTP errors may resolve on retry |
| `CapabilityProbeError` | All probe symbol/bars attempts exhausted | Non-fatal — `AuthManager` logs a warning and retains the plan-based estimate |

---

## Environment Variables

| Variable | Effect |
|----------|--------|
| `TVKIT_BROWSER` | Sets `browser` when no credential kwarg is provided. Must be `"chrome"` or `"firefox"`. |
| `TVKIT_AUTH_TOKEN` | Sets `auth_token` when no credential kwarg is provided. |

`TVKIT_BROWSER` and `TVKIT_AUTH_TOKEN` are mutually exclusive. Setting both raises `ValueError` at `OHLCV()` construction.

---

## Quick Usage Examples

**Anonymous (default — zero changes required):**

```python
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV() as client:
    bars = await client.get_historical_ohlcv(
        exchange_symbol="NASDAQ:AAPL",
        interval="1D",
        bars_count=100,
    )
```

**Browser cookie extraction (Chrome):**

```python
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV(browser="chrome") as client:
    account = client.account
    if account is not None:
        print(f"Plan: {account.plan!r}, tier: {account.tier}, max_bars: {account.max_bars}")
    bars = await client.get_historical_ohlcv(
        exchange_symbol="NASDAQ:AAPL",
        interval="1D",
        bars_count=10_000,
    )
```

**Direct token injection (CI/CD environments):**

```python
import os
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV(auth_token=os.environ["TVKIT_AUTH_TOKEN"]) as client:
    bars = await client.get_historical_ohlcv(
        exchange_symbol="BINANCE:BTCUSDT",
        interval="1H",
        bars_count=500,
    )
```

**Using `AuthManager` directly:**

```python
from tvkit.auth import AuthManager, TradingViewCredentials

creds = TradingViewCredentials(browser="firefox")
async with AuthManager(creds) as auth:
    print(auth.auth_token)   # real TradingView auth token
    print(auth.account)      # TradingViewAccount(...)
```

---

## Reference Pages

- [TradingViewCredentials](credentials.md) — constructor parameters, env vars, validation rules
- [TradingViewAccount](account.md) — all fields, probe lifecycle, PII masking
- [AuthManager](manager.md) — context manager lifecycle, properties, exception table

---

## See Also

- [Concepts: Account Capabilities](../../concepts/capabilities.md)
- [Guide: Authenticated Sessions](../../guides/authenticated-sessions.md)
- [OHLCV Client Reference](../chart/ohlcv.md)
- [Limitations: Authentication Limitations](../../limitations.md#authentication-limitations)
- [TradingView Pricing](https://www.tradingview.com/pricing/)
