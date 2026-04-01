# Using tvkit in Google Colab (and Other Hosted Notebooks)

[Home](../index.md) > Guides > Notebook / Colab

Google Colab runs on a remote Google machine — it has no access to your local Chrome or Firefox cookie store. `OHLCV(browser=...)` therefore cannot work directly in Colab.

This guide shows how to export your TradingView session cookies **from your own computer** and pass them into a Colab notebook so that tvkit can authenticate on your behalf.

---

## Why Browser Mode Fails in Colab

| Mode | Local script | Colab notebook |
| --- | --- | --- |
| `OHLCV()` — anonymous | ✅ Works | ✅ Works (5,000-bar free limit) |
| `OHLCV(browser="chrome")` | ✅ Works | ❌ No local browser available |
| `OHLCV(cookies={...})` | ✅ Works | ✅ Works — **use this in Colab** |
| `OHLCV(auth_token=...)` | ✅ Works | ✅ Works (5,000 bars/segment — see [note](#alternative-direct-auth_token-injection)) |

> **`cookies={...}` is the recommended mode for Colab.** It performs a full TradingView profile fetch, populates `account.tier` and `account.max_bars` (plan-based estimate), and automatically uses the `prodata.tradingview.com` premium endpoint for paid accounts (up to 40,000 bars per fetch). See [Account Capabilities](../concepts/capabilities.md#premium-websocket-endpoint).

---

## Step 1 — Export Cookies from Your Host Computer

Run the interactive export script **locally** (not in Colab). It reads your browser's TradingView cookies and lets you copy or save the result.

**Prerequisites:** log in to TradingView in Chrome or Firefox before running.

```bash
uv run python scripts/export_tv_cookies.py
```

The script will:

1. Ask which browser to read from (Chrome or Firefox).
2. Extract TradingView cookies via tvkit's built-in cookie provider.
3. Show a summary table — cookie names only, no values on screen yet.
4. Filter to the **5 auth-essential cookies** (`sessionid`, `sessionid_sign`, `csrftoken`, `device_t`, `tv_ecuid`) and export only those. The full cookie jar also contains analytics and consent cookies that are not needed and make the JSON too large for Colab Secrets to store reliably.
5. Print the filtered JSON between clear dashed delimiters for accurate copy-paste.
6. Show copy-paste Colab instructions on request.

Example output (values redacted here — the script prints real values):

```text
╭──────────────────────────────────╮
│ Cookies found in Chrome          │
├──────────────────┬───────────────┤
│ Cookie name      │ Status        │
├──────────────────┼───────────────┤
│ csrftoken        │ ✓ present     │
│ device_t         │ ✓ present     │
│ sessionid        │ ✓ present     │
│ sessionid_sign   │ ✓ present     │
│ tv_ecuid         │ ✓ present     │
╰──────────────────┴───────────────╯

✓ Extracted 12 cookie(s).
```

If `sessionid` is missing, log in to TradingView in the browser and re-run.

> **Security:** the exported JSON is your TradingView session credential. Do not commit it to git or paste it into a public notebook. Add `tv_cookies.json` to `.gitignore` if you save it to a file.

---

## Step 2 — Store the JSON in Colab Secrets

Colab has a built-in secrets manager that keeps values private to your account — use it instead of pasting credentials directly into a cell.

1. Open your Colab notebook.
2. Click the **key icon (🔑)** in the left sidebar → **Add new secret**.
3. Set **Name** to `TV_COOKIES`.
4. Paste the full JSON line from the export script as the **Value**.
5. Enable **Notebook access** for the secret.

---

## Step 3 — Use the Cookies in Colab

### Verify the secret before using it

If you get `JSONDecodeError` when calling `json.loads(userdata.get("TV_COOKIES"))`, run this diagnostic cell first:

```python
from google.colab import userdata

raw = userdata.get("TV_COOKIES")
print(f"Length: {len(raw)}")
print(f"Starts with '{{': {raw.startswith('{')}")
print(f"Ends with '}}': {raw.endswith('}')}")
```

A correct value starts with `{` and ends with `}`. If it is truncated or missing the closing `}`, re-run the export script and update the secret.

If those checks pass but `json.loads(...)` still fails, the secret was usually copied in a format that is not strict JSON anymore, for example:

- It was pasted as a Python dict literal instead of JSON.
- It was wrapped in an extra layer of quotes.
- It contains terminal copy-paste artifacts.

Use the safer loader below instead of calling `json.loads(userdata.get("TV_COOKIES"))` directly.

### Cell 1 — Install tvkit

```python
!pip install tvkit -q
```

### Cell 2 — Load cookies from Colab Secrets

```python
import ast
import json
from google.colab import userdata

def load_colab_cookies() -> dict[str, str]:
    """Parse TV_COOKIES from Colab Secrets, tolerating common paste mistakes."""
    raw = userdata.get("TV_COOKIES")
    text = raw.strip()
    if not text:
        raise ValueError("TV_COOKIES is empty — add it in the 🔑 Secrets panel")

    # Handle accidental wrapping in outer quotes.
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: terminal copy sometimes produces a Python dict literal.
        parsed = ast.literal_eval(text)

    if isinstance(parsed, str):
        parsed = json.loads(parsed)
    if not isinstance(parsed, dict):
        raise TypeError("TV_COOKIES must decode to a dict — check the secret value")

    cookies = {str(k): str(v) for k, v in parsed.items()}
    if "sessionid" not in cookies:
        raise ValueError(
            "TV_COOKIES is missing 'sessionid' — re-run scripts/export_tv_cookies.py"
        )
    return cookies

cookies = load_colab_cookies()
print(f"✓ Cookies loaded ({len(cookies)} keys)")
```

### Cell 3 — Fetch historical bars

```python
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.auth import ProfileFetchError, AuthError

SYMBOL   = "BINANCE:BTCUSDT"
INTERVAL = "1H"
N_BARS   = 10_000

async def fetch_bars():
    async with OHLCV(cookies=cookies) as client:
        account = client.account
        if account:
            print(f"Logged in:  {account.username}")
            print(f"Plan:       {account.plan}  |  Tier: {account.tier}")
            print(f"Max bars:   {account.max_bars}")

        bars = await client.get_historical_ohlcv(
            exchange_symbol=SYMBOL,
            interval=INTERVAL,
            bars_count=N_BARS,
        )
        print(f"\nFetched {len(bars):,} bars")
        return bars

try:
    bars = await fetch_bars()
except ProfileFetchError:
    print("❌ Cookies rejected — re-run export_tv_cookies.py and update TV_COOKIES in Secrets.")
    raise
except AuthError as e:
    print(f"❌ Auth error: {e}")
    raise
```

Colab notebooks already run an event loop — use top-level `await` in cells, not `asyncio.run(...)`.

`account.max_bars` is a plan-based estimate derived from your TradingView plan (e.g., 20,000 for Premium). It is available immediately after the context manager opens.

### Cell 4 — Display results as a table

```python
from datetime import UTC, datetime
import pandas as pd

df = pd.DataFrame(
    {
        "datetime": [
            datetime.fromtimestamp(b.timestamp, tz=UTC).strftime("%Y-%m-%d %H:%M")
            for b in bars
        ],
        "open":   [b.open   for b in bars],
        "high":   [b.high   for b in bars],
        "low":    [b.low    for b in bars],
        "close":  [b.close  for b in bars],
        "volume": [b.volume for b in bars],
    }
)

print(f"{SYMBOL} [{INTERVAL}] — {len(df):,} bars")
df.tail(10)          # Colab renders DataFrames as formatted HTML tables
```

`df.tail(10)` as the last expression in a cell renders the DataFrame as a styled HTML table in Colab output. Use `df.head(10)` to see the oldest bars, or `df` for the full set (slow for 10k+ rows).

---

## Handling Errors

In `cookies={...}` mode, errors surface as `ProfileFetchError` (the library makes an HTTP request to TradingView using the cookies — not a browser extraction). `BrowserCookieError` is **not** raised in this mode.

| Error | Cause | Fix |
| --- | --- | --- |
| `ProfileFetchError` | Cookies are expired, invalid, or the JSON is malformed | Re-run the export script and update `TV_COOKIES` in Secrets |
| `AuthError` | Token rejected by TradingView WebSocket | Session expired — re-export cookies |

```python
try:
    bars = await fetch_bars()
except ProfileFetchError:
    print(
        "Cookies rejected by TradingView.\n"
        "Re-run scripts/export_tv_cookies.py and update the TV_COOKIES secret."
    )
except AuthError as e:
    print(f"Auth error: {e}")
```

---

## Alternative: Direct `auth_token` Injection

If you already have a TradingView `auth_token` string (a JWT), you can inject it directly. This is simpler but has an important limitation.

> **Limitation:** `auth_token=...` mode skips the profile fetch. `account` is `None`, the account tier is unknown, and tvkit uses the standard `data.tradingview.com` endpoint capped at 5,000 bars per segment — regardless of your actual account tier. See [Limitations — Direct Token Mode](../limitations.md#direct-token-mode-does-not-use-the-premium-endpoint).

```python
import os
from google.colab import userdata
from tvkit.api.chart.ohlcv import OHLCV

auth_token = userdata.get("TV_AUTH_TOKEN")  # store your token in Colab Secrets

async def fetch():
    async with OHLCV(auth_token=auth_token) as client:
        # account is None — no plan info available in this mode
        bars = await client.get_historical_ohlcv(
            exchange_symbol="BINANCE:BTCUSDT",
            interval="1H",
            bars_count=5_000,
        )
        return bars

bars = await fetch()
```

To get your `auth_token`, open TradingView in a browser, open DevTools → Application → Cookies → find `tradingview.com`, and copy the `auth_token` cookie value. Store it as the Colab secret `TV_AUTH_TOKEN`.

---

## Local Jupyter / VS Code Notebooks

If your notebook runs **locally** (Jupyter, VS Code, JupyterLab), browser mode works directly:

```python
from tvkit.api.chart.ohlcv import OHLCV

async def fetch():
    async with OHLCV(browser="chrome") as client:
        account = client.account
        if account:
            print(f"Tier: {account.tier}  |  Max bars: {account.max_bars}")
        return await client.get_historical_ohlcv("BINANCE:BTCUSDT", "1H", 10_000)

bars = await fetch()
```

If you are running a local notebook kernel that does not support top-level `await`, use:

```python
# pip install nest_asyncio
import nest_asyncio
nest_asyncio.apply()

import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def fetch():
    async with OHLCV(browser="chrome") as client:
        return await client.get_historical_ohlcv("BINANCE:BTCUSDT", "1H", 10_000)

bars = await fetch()  # use await directly in Jupyter cells
```

---

## Security Checklist

- [ ] Never paste cookies or tokens directly into a shared or public notebook cell
- [ ] Use Colab Secrets, not `os.environ[...] = "..."` in a cell
- [ ] Add `tv_cookies.json` to `.gitignore` if you save the export to a file
- [ ] Do not commit cookie values to git
- [ ] Re-export cookies when you see `ProfileFetchError` — your TradingView session has expired

---

## See Also

- [Authenticated Sessions Guide](authenticated-sessions.md) — full local authentication workflow
- [Account Capabilities](../concepts/capabilities.md) — plan tiers, `max_bars`, prodata endpoint
- [Authentication Limitations](../limitations.md#authentication-limitations) — known constraints
- [tvkit.auth Reference](../reference/auth/index.md) — `TradingViewCredentials`, `AuthManager`
