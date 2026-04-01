# `AuthManager` Reference

**Module:** `tvkit.auth.auth_manager`
**Class:** `AuthManager`
**Available since:** v0.7.0

Async context manager that orchestrates the full TradingView authentication lifecycle. Used internally by `OHLCV` — most users interact with `AuthManager` only indirectly through `OHLCV` constructor parameters and `client.account`. Direct use is supported for advanced scenarios.

---

## Import

```python
from tvkit.auth import AuthManager
```

---

## Constructor

```python
class AuthManager:
    def __init__(
        self,
        credentials: TradingViewCredentials | None = None,
    ) -> None: ...
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `credentials` | `TradingViewCredentials \| None` | `None` | Authentication credentials. `None` defaults to anonymous mode (same as `TradingViewCredentials()`). |

---

## Authentication Modes

`AuthManager` behavior depends on the credential mode:

| Mode | `credentials` | `auth_token` after `__aenter__` | `account` | Background probe |
|------|--------------|--------------------------------|-----------|-----------------|
| **Anonymous** | `None` or `TradingViewCredentials()` | `"unauthorized_user_token"` | `None` | Not launched |
| **Browser** | `TradingViewCredentials(browser=...)` | Real TradingView auth token | `TradingViewAccount` | Launched |
| **Cookie dict** | `TradingViewCredentials(cookies=...)` | Real TradingView auth token | `TradingViewAccount` | Launched |
| **Direct token** | `TradingViewCredentials(auth_token=...)` | The provided token | `None` | Not launched |

---

## `__aenter__`

```python
async def __aenter__(self) -> "AuthManager": ...
```

Authenticates and returns the manager.

**For browser / cookie-dict mode:**

1. Extracts or uses provided cookies
2. Issues authenticated `GET https://www.tradingview.com/` to obtain `auth_token` and user profile
3. Estimates `max_bars` from the plan slug using `CapabilityDetector`
4. Builds a `TradingViewAccount`
5. Launches the background capability probe task

**For direct-token mode:** Sets `auth_token` from credentials; skips all cookie and profile steps; `account` remains `None`.

**For anonymous mode:** Sets `auth_token = "unauthorized_user_token"`; skips all auth steps.

### Raises

| Exception | When |
|-----------|------|
| `BrowserCookieError` | Browser cookie extraction fails — `browser_cookie3` not installed, `sessionid` missing, or browser database locked |
| `ProfileFetchError` | TradingView homepage bootstrap parse fails, `user` is null/empty, `auth_token` is missing or too short, or HTTP 5xx |

---

## `__aexit__`

```python
async def __aexit__(
    self,
    exc_type: type[BaseException] | None,
    exc_val: BaseException | None,
    exc_tb: types.TracebackType | None,
) -> None: ...
```

Cancels the background probe task (if running) and closes the probe WebSocket connection. Runs in all exit paths — normal return, exception, and cancellation.

---

## Properties

### `auth_token`

```python
@property
def auth_token(self) -> str: ...
```

The current TradingView auth token for WebSocket authentication. Must only be accessed after `__aenter__` has completed.

### `account`

```python
@property
def account(self) -> TradingViewAccount | None: ...
```

The authenticated account profile, or `None` in anonymous and direct-token modes.

---

## Advanced Properties

The following properties are part of the public API but intended for use by `ConnectionService` and other internal components — not for typical user code.

### `cookie_provider`

```python
@property
def cookie_provider(self) -> CookieProvider | None: ...
```

The `CookieProvider` instance (browser mode only), or `None` in all other modes. Allows the connection service to invalidate the cookie cache before re-extraction on a WebSocket auth error.

### `token_provider`

```python
@property
def token_provider(self) -> TokenProvider | None: ...
```

The `TokenProvider` instance (browser / cookie-dict modes), or `None` in anonymous and direct-token modes. Allows the connection service to trigger a token refresh on a WebSocket auth error.

---

## Background Probe Task

In browser and cookie-dict modes, `__aenter__` launches a background `asyncio.Task` that:

1. Opens a short-lived dedicated WebSocket connection
2. Requests daily bars using an adaptive bars_count strategy (`50,000` → `40,000` → `20,000`)
3. Uses a symbol fallback chain (`NASDAQ:AAPL` → `BINANCE:BTCUSDT` → `INDEX:SPX`)
4. Updates `account.max_bars`, `account.probe_confirmed`, `account.max_bars_source`, and `account.probe_status` when it completes

`CapabilityProbeError` is non-fatal — `AuthManager` logs a `WARNING` and retains the plan-based estimate if the probe fails. The probe does not affect the primary OHLCV connection.

`__aexit__` cancels the probe task if it is still running. Call `OHLCV.wait_until_ready()` to explicitly wait for the probe to finish before your first fetch.

---

## Usage Examples

**Used via `OHLCV` — recommended for most use cases:**

```python
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV(browser="chrome") as client:
    account = client.account
    bars = await client.get_historical_ohlcv(
        exchange_symbol="NASDAQ:AAPL",
        interval="1D",
        bars_count=1000,
    )
```

**Used directly — advanced:**

```python
from tvkit.auth import AuthManager, TradingViewCredentials

# Anonymous
async with AuthManager() as auth:
    token = auth.auth_token   # "unauthorized_user_token"
    account = auth.account    # None

# Browser cookie extraction
creds = TradingViewCredentials(browser="chrome")
async with AuthManager(credentials=creds) as auth:
    token = auth.auth_token   # real TradingView auth token
    account = auth.account    # TradingViewAccount(tier="premium", ...)

# Direct token injection
creds = TradingViewCredentials(auth_token="tv_auth_token_here")
async with AuthManager(credentials=creds) as auth:
    token = auth.auth_token   # the injected token
    account = auth.account    # None
```

---

## See Also

- [TradingViewCredentials Reference](credentials.md)
- [TradingViewAccount Reference](account.md)
- [Concepts: Account Capabilities](../../concepts/capabilities.md)
- [Guide: Authenticated Sessions](../../guides/authenticated-sessions.md)
- [OHLCV Client Reference](../chart/ohlcv.md)
