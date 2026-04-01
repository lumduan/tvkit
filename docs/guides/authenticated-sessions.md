# Authenticated Sessions

**Available since:** v0.7.0

This guide covers everything you need to use tvkit with an authenticated TradingView account: when to authenticate, which credential mode to choose, how to inspect capabilities, and how to handle failures.

---

## When to Authenticate

Anonymous sessions work out of the box with no changes required — all pre-v0.7.0 code continues to work unchanged.

| Use case | Recommended mode |
|----------|-----------------|
| Quick scripts, experimentation | Anonymous |
| Fetching more than 5,000 bars per request | Authenticated (browser or token) |
| Production pipelines on a paid account | Authenticated (token injection or browser) |
| CI/CD or headless servers | Token injection (`auth_token`) or cookie dict (`cookies`) |

---

## Choosing a Credential Mode

### Browser cookie extraction (recommended for interactive use)

tvkit reads session cookies from your already-logged-in Chrome or Firefox browser using `browser_cookie3`.

```python
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV(browser="chrome") as client:
    bars = await client.get_historical_ohlcv(
        exchange_symbol="NASDAQ:AAPL",
        interval="1D",
        bars_count=10_000,
    )
```

**Requirements:**

- You must be logged in to TradingView in Chrome or Firefox **before** running tvkit
- Only `"chrome"` and `"firefox"` are supported in v0.7.0

If cookie extraction fails (e.g., browser database is locked, session is expired, or `browser_cookie3` cannot access the browser's keychain), a `BrowserCookieError` is raised. See [Failure Recovery](#failure-recovery) below.

**Multi-profile setup:** If you have multiple Chrome or Firefox profiles, specify the profile name:

```python
async with OHLCV(browser="chrome", browser_profile="Profile 2") as client:
    ...
```

### Direct token injection (recommended for CI/CD)

For headless servers, CI/CD pipelines, or environments without a desktop browser, inject the token directly. tvkit will use it as-is with no cookie extraction or profile fetch.

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

**Trade-off:** No profile fetch and no capability detection in this mode — `client.account` is `None`. tvkit does not know your plan tier and cannot auto-configure `max_bars`. Segmented fetching defaults to 5,000 bars per segment (the free-tier conservative limit). If your account supports more, pass a larger `bars_count` explicitly or use browser mode instead.

**Token refresh:** tvkit cannot refresh the token automatically in this mode. You are responsible for providing a valid, non-expired token.

### Cookie dict injection (advanced CI/CD)

Pass pre-extracted cookies as a dict. Useful when you can extract cookies from a CI secret store or a browser automation tool. This mode performs a profile fetch, so `client.account` is populated.

```python
from tvkit.api.chart.ohlcv import OHLCV

cookies = {"sessionid": "...", "csrftoken": "..."}
async with OHLCV(cookies=cookies) as client:
    bars = await client.get_historical_ohlcv(
        exchange_symbol="NASDAQ:AAPL",
        interval="1D",
        bars_count=5_000,
    )
```

Cookie extraction and refresh are the caller's responsibility.

### Anonymous (default)

No credentials. All existing code continues to work unchanged — 5,000-bar free-tier limits apply.

```python
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV() as client:
    bars = await client.get_historical_ohlcv(
        exchange_symbol="NASDAQ:AAPL",
        interval="1D",
        bars_count=100,
    )
```

---

## Environment Variables

Credentials can also be configured via environment variables. tvkit reads them only when no explicit credential kwarg is provided.

| Variable | Effect |
|----------|--------|
| `TVKIT_BROWSER` | Equivalent to `OHLCV(browser="chrome")` or `OHLCV(browser="firefox")` |
| `TVKIT_AUTH_TOKEN` | Equivalent to `OHLCV(auth_token=...)` |

```bash
export TVKIT_BROWSER=chrome
```

```python
# No kwarg needed — TVKIT_BROWSER is picked up automatically
async with OHLCV() as client:
    ...
```

`TVKIT_BROWSER` and `TVKIT_AUTH_TOKEN` are mutually exclusive. Setting both raises `ValueError`.

---

## Typical Startup Flow

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.auth import BrowserCookieError, ProfileFetchError

async def main() -> None:
    try:
        async with OHLCV(browser="chrome") as client:
            # 1. Account profile is available immediately after __aenter__
            account = client.account
            if account:
                print(f"Authenticated: tier={account.tier!r}, max_bars={account.max_bars}")

            # 2. Optionally wait for the background probe to confirm max_bars
            await client.wait_until_ready()
            if account:
                print(f"Probe: status={account.probe_status!r}, source={account.max_bars_source!r}")

            # 3. Fetch data — max_bars is automatically used for segmentation
            bars = await client.get_historical_ohlcv(
                exchange_symbol="NASDAQ:AAPL",
                interval="1",
                bars_count=50_000,
            )
            print(f"Fetched {len(bars)} bars")

    except BrowserCookieError as e:
        print(f"Browser error: {e}")
        print("Fix: Log in to TradingView in Chrome, then run again.")
    except ProfileFetchError as e:
        print(f"Profile error: {e}")
        print("Fix: Your session may have expired. Log out and back in to TradingView.")

asyncio.run(main())
```

---

## Checking Capabilities

After `__aenter__`, inspect `client.account` to understand your current limits:

```python
async with OHLCV(browser="chrome") as client:
    account = client.account

    if account is None:
        # Anonymous or direct-token mode
        print("No account info — 5,000-bar default applies")
    else:
        print(f"TradingView plan:  {account.plan!r}")
        print(f"Tier:              {account.tier!r}")
        print(f"Max bars:          {account.max_bars}")
        print(f"Source:            {account.max_bars_source!r}")
        print(f"Probe status:      {account.probe_status!r}")
        print(f"Probe confirmed:   {account.probe_confirmed}")
```

See [TradingView Pricing](https://www.tradingview.com/pricing/) for the full plan comparison and the [Account Capabilities concept page](../concepts/capabilities.md) for how plan slugs map to tvkit tiers.

---

## Waiting for Probe Readiness

The background capability probe runs asynchronously. For most use cases, the plan-based estimate available immediately after `__aenter__` is sufficient. If you need probe-confirmed `max_bars` before your first fetch:

```python
async with OHLCV(browser="chrome") as client:
    await client.wait_until_ready()  # waits for background probe

    account = client.account
    if account:
        print(f"Confirmed max_bars: {account.max_bars} (source: {account.max_bars_source!r})")
```

`wait_until_ready()` adds startup latency equal to the probe duration (typically a few seconds). If the probe fails or is cancelled, the method returns without raising and the plan estimate remains in effect.

---

## Failure Recovery

### `BrowserCookieError`

Raised when session cookies cannot be extracted from the browser.

**Common causes:**

- Not logged in to TradingView in the specified browser
- Browser database is locked (browser still running on some Linux setups)
- macOS Keychain prompt was dismissed (Chrome on macOS)

**Fix:** Log in to TradingView in Chrome or Firefox, close the browser if it holds a database lock, then re-run tvkit.

**Fallback:** Use `cookies={...}` or `auth_token=...` if browser extraction is not reliable in your environment.

### `ProfileFetchError`

Raised when the TradingView user profile cannot be extracted from the homepage bootstrap.

**Common causes:**

- Browser session has expired (cookies are stale)
- TradingView returned HTTP 5xx (transient server error)
- TradingView changed the homepage HTML structure (requires a tvkit update)

**Fix:** Log out of TradingView in your browser and log back in to refresh the session cookies, then re-run tvkit. For transient HTTP errors, simply retry.

### `AuthError` during streaming

If TradingView rejects the auth token during an active WebSocket session, `AuthError` is raised from the generator. Re-enter the `OHLCV` context manager to trigger fresh cookie extraction:

```python
from tvkit.auth import AuthError

for attempt in range(3):
    try:
        async with OHLCV(browser="chrome") as client:
            async for bar in client.get_ohlcv(
                exchange_symbol="NASDAQ:AAPL",
                interval="1",
            ):
                # process bar here
                pass
    except AuthError:
        print(f"Auth error on attempt {attempt + 1} — re-entering context manager")
        continue
    break
```

---

## Security Notes

- **No credential persistence (browser mode):** In browser mode, tvkit never writes session cookies to disk. Each `OHLCV()` context manager entry re-extracts fresh cookies from the browser's local profile. The probe result cache writes only the confirmed `max_bars` integer — never credentials.
- **Masked logging:** Cookie values and token values are never logged. `TradingViewAccount.__repr__` shows only the first three characters of the username.
- **Requests to TradingView only:** The auth token is used for two TradingView-owned services only — the authenticated homepage GET (browser/cookie-dict modes) to fetch the user profile, and the data WebSocket for OHLCV streaming. tvkit makes no requests to any other endpoint.
- **Local machine trust:** Browser cookie extraction reads from your local browser profile. Run tvkit only on machines you trust. On shared or multi-user systems, prefer `auth_token` injection from a secured secret store.

---

## See Also

- [Concepts: Account Capabilities](../concepts/capabilities.md)
- [TradingViewCredentials Reference](../reference/auth/credentials.md)
- [TradingViewAccount Reference](../reference/auth/account.md)
- [AuthManager Reference](../reference/auth/manager.md)
- [OHLCV Client Reference](../reference/chart/ohlcv.md)
- [Limitations: Authentication Limitations](../limitations.md#authentication-limitations)
- [TradingView Pricing](https://www.tradingview.com/pricing/)
