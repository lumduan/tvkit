# `TradingViewCredentials` Reference

**Module:** `tvkit.auth.credentials`
**Class:** `TradingViewCredentials`
**Available since:** v0.7.0

Credentials dataclass for TradingView authentication. Provide exactly one credential source — `browser`, `cookies`, or `auth_token` — or omit all for anonymous mode.

---

## Import

```python
from tvkit.auth import TradingViewCredentials
```

---

## Constructor

```python
@dataclass
class TradingViewCredentials:
    browser: str | None = None
    browser_profile: str | None = None
    cookies: dict[str, str] | None = None  # excluded from repr
    auth_token: str | None = None           # excluded from repr
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `browser` | `str \| None` | `None` | Browser to extract session cookies from. Must be `"chrome"` or `"firefox"`. Mutually exclusive with `cookies` and `auth_token`. |
| `browser_profile` | `str \| None` | `None` | Specific browser profile name (e.g. `"Default"`, `"Profile 2"`). Only valid when `browser` is set. Handles multi-profile setups. Cannot be set via environment variable. |
| `cookies` | `dict[str, str] \| None` | `None` | Pre-extracted cookie dict (name → value). Mutually exclusive with `browser` and `auth_token`. Advanced fallback for CI/CD or headless environments. |
| `auth_token` | `str \| None` | `None` | Pre-obtained TradingView auth token. Mutually exclusive with `browser` and `cookies`. No profile fetch is performed; no capability probe is launched; `client.account` is `None` in this mode. |

`cookies` and `auth_token` are excluded from `repr` to prevent credential leakage in logs.

---

## Credential Modes

### Anonymous (default)

All fields `None`. Uses `"unauthorized_user_token"` during WebSocket initialization — the same anonymous token as all pre-v0.7.0 sessions. No profile fetch; no capability probe; `client.account` is `None`.

```python
creds = TradingViewCredentials()
assert creds.is_anonymous  # True
```

### Browser cookie extraction

tvkit extracts session cookies from the named browser using `browser_cookie3`. The user must be logged in to TradingView in that browser before running tvkit. If TradingView rejects the token during the WebSocket session, `AuthError` is raised — re-enter the `OHLCV` context manager to trigger fresh cookie extraction.

```python
creds = TradingViewCredentials(browser="chrome")
creds = TradingViewCredentials(browser="firefox", browser_profile="Profile 2")
```

### Cookie dict injection

Pre-extracted cookie dict. Advanced fallback for environments without a desktop browser (CI/CD, headless servers). The caller is responsible for providing valid, non-expired cookies containing at least `sessionid`.

```python
creds = TradingViewCredentials(cookies={"sessionid": "...", "csrftoken": "..."})
```

### Direct token injection

Pre-obtained TradingView auth token. Bypasses cookie extraction and profile fetch entirely. No capability probe is launched; `client.account` is `None`. The caller is responsible for token refresh.

```python
creds = TradingViewCredentials(auth_token="tv_auth_token_here")
```

---

## Supported Combinations

| `browser` | `cookies` | `auth_token` | Valid | Mode |
|-----------|-----------|-------------|-------|------|
| `None` | `None` | `None` | ✅ | Anonymous |
| `"chrome"` / `"firefox"` | `None` | `None` | ✅ | Browser |
| `None` | `{...}` | `None` | ✅ | Cookie dict |
| `None` | `None` | `"token"` | ✅ | Direct token |
| Any two set | — | — | ❌ | `ValueError` at construction |

---

## Credential Precedence (via `OHLCV`)

When creating `OHLCV()`, credentials are resolved in this order:

1. **Constructor kwargs** (`browser`, `cookies`, `auth_token`) — highest priority
2. **Environment variables** (`TVKIT_BROWSER`, `TVKIT_AUTH_TOKEN`) — only consulted when no explicit credential kwarg is provided
3. **Anonymous mode** — fallback when nothing is set

Environment variables are **not** consulted if any credential kwarg is provided. This prevents silent XOR violations when an env var is set alongside a kwarg.

### Environment Variables

| Variable | Equivalent to | Notes |
|----------|--------------|-------|
| `TVKIT_BROWSER` | `browser="chrome"` or `browser="firefox"` | Must be exactly `"chrome"` or `"firefox"` |
| `TVKIT_AUTH_TOKEN` | `auth_token="..."` | Any non-empty string |

`TVKIT_BROWSER` and `TVKIT_AUTH_TOKEN` are mutually exclusive. Setting both raises `ValueError` at `OHLCV()` construction (not at `TradingViewCredentials` construction, since env vars are read by `OHLCV`).

`browser_profile` cannot be configured via environment variable — use the `browser_profile` kwarg.

---

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_anonymous` | `bool` | `True` if all fields are `None` |
| `uses_browser` | `bool` | `True` if browser cookie extraction is configured |
| `uses_cookie_dict` | `bool` | `True` if a pre-extracted cookie dict was provided |
| `uses_direct_token` | `bool` | `True` if a pre-obtained `auth_token` was provided |

---

## Raises

`ValueError` is raised at `TradingViewCredentials` construction if:

- More than one of `browser`, `cookies`, or `auth_token` is provided
- `browser` is not `"chrome"` or `"firefox"`
- `browser_profile` is set without `browser`

`ValueError` is raised at `OHLCV()` construction if:

- Both `TVKIT_BROWSER` and `TVKIT_AUTH_TOKEN` environment variables are set (and no explicit credential kwarg overrides them)

---

## Examples

```python
from tvkit.auth import TradingViewCredentials

# Anonymous — no credentials
creds = TradingViewCredentials()
assert creds.is_anonymous

# Chrome, default profile
creds = TradingViewCredentials(browser="chrome")
assert creds.uses_browser

# Firefox, specific profile
creds = TradingViewCredentials(browser="firefox", browser_profile="default")

# Cookie dict (CI/CD)
creds = TradingViewCredentials(cookies={"sessionid": "abc123"})
assert creds.uses_cookie_dict

# Direct token
creds = TradingViewCredentials(auth_token="tv_auth_token_here")
assert creds.uses_direct_token

# Invalid — raises ValueError
TradingViewCredentials(browser="chrome", auth_token="token")  # XOR violation
TradingViewCredentials(browser_profile="Default")              # profile without browser
TradingViewCredentials(browser="safari")                       # unsupported browser
```

---

## See Also

- [AuthManager Reference](manager.md)
- [TradingViewAccount Reference](account.md)
- [OHLCV Client Reference](../chart/ohlcv.md)
- [Guide: Authenticated Sessions](../../guides/authenticated-sessions.md)
- [Concepts: Account Capabilities](../../concepts/capabilities.md)
