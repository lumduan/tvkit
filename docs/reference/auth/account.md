# `TradingViewAccount` Reference

**Module:** `tvkit.auth.models`
**Class:** `TradingViewAccount`
**Available since:** v0.7.0

Dataclass holding the authenticated account profile and detected capability limits. Available via `client.account` after entering the `OHLCV` context manager with browser or cookie-dict credentials.

---

## Import

```python
from tvkit.auth import TradingViewAccount
```

---

## Fields

| Field | Type | Mutable | Description |
|-------|------|---------|-------------|
| `user_id` | `int` | No | TradingView numeric user ID |
| `username` | `str` | No | TradingView display username |
| `plan` | `str` | No | Raw `pro_plan` value from TradingView profile (e.g. `"pro_premium"`, `"ultimate"`). Preserved verbatim from the bootstrap payload. |
| `tier` | `str` | No | Normalized tier: one of `"free"`, `"pro"`, `"premium"`, `"ultimate"`. See [Account Capabilities](../../concepts/capabilities.md) for the mapping table. |
| `is_pro` | `bool` | No | `True` if the account has any paid subscription |
| `is_broker` | `bool` | No | `True` if the account has broker capabilities |
| `max_bars` | `int` | **Yes** | Current maximum bars per historical fetch. Starts as the plan-based estimate; updated by the background probe when confirmed. Guarded by `_lock` for concurrent access safety. |
| `estimated_max_bars` | `int` | No | Immutable plan-based estimate captured at login. Never mutated — used for debugging and observability only. |
| `probe_confirmed` | `bool` | Yes | `True` once the background probe has confirmed the actual server-enforced `max_bars`. |
| `max_bars_source` | `Literal["estimate", "probe"]` | Yes | Source of the current `max_bars` value. `"estimate"` immediately after login; changes to `"probe"` when confirmed. |
| `probe_status` | `Literal["pending", "success", "throttled", "failed"]` | Yes | Current probe lifecycle state. See [probe_status](#probe_status-states) below. |

`max_bars`, `probe_confirmed`, `max_bars_source`, and `probe_status` are updated in-place by the background capability probe.

---

## `plan` vs `tier`

| TradingView plan | `plan` (raw) | `tier` (normalized) |
|------------------|-------------|---------------------|
| Basic (free) | `""` | `"free"` |
| Essential | `"pro"` | `"pro"` |
| Plus | `"pro_plus"` | `"pro"` |
| Premium | `"pro_premium"` | `"premium"` |
| Ultimate | `"ultimate"` | `"ultimate"` |

Use `tier` for capability logic. Use `plan` only for debugging or display purposes.

---

## `max_bars` Concurrency

`max_bars` is updated by the background probe task. All updates are guarded by an internal `asyncio.Lock` to prevent race conditions when multiple coroutines use the session concurrently.

`SegmentedFetchService` snapshots `max_bars` once at the start of each fetch to ensure stable segment boundaries throughout a single request, even if the probe updates `max_bars` mid-flight.

---

## `estimated_max_bars`

Immutable after construction. Captures the plan-based estimate at the time of login. Useful for comparing the estimate against the probe-confirmed value:

```python
account = client.account
if account.probe_confirmed:
    diff = account.estimated_max_bars - account.max_bars
    print(f"Probe adjusted max_bars by {diff} bars")
```

---

## `probe_status` States

```
pending → success
       → throttled
       → failed
```

| State | Meaning |
|-------|---------|
| `"pending"` | Probe not yet started or still in progress |
| `"success"` | Probe confirmed `max_bars`; `max_bars_source` is `"probe"` |
| `"throttled"` | All probe bars_count attempts were rate-limited; `estimated_max_bars` retained |
| `"failed"` | All symbol + bars combinations exhausted; `estimated_max_bars` retained |

`"throttled"` and `"failed"` are non-fatal — the session continues with the plan estimate.

---

## `__repr__` and PII Masking

`TradingViewAccount.__repr__` masks the username to prevent personally identifiable information from appearing in logs:

```python
# Account with username "johndoe"
print(repr(account))
# TradingViewAccount(user_id=123456, username='joh***', plan='pro_premium', ...)
```

Only the first three characters of the username are shown; the remainder is replaced with `***`. `user_id` and `plan` are shown in full.

---

## `from_profile()` Class Method

```python
@classmethod
def from_profile(
    cls,
    profile: dict[str, Any],
    max_bars: int,
    tier: str,
) -> "TradingViewAccount": ...
```

Constructs a `TradingViewAccount` from a parsed TradingView user profile dict. Used internally by `AuthManager`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `profile` | `dict[str, Any]` | Parsed `user` object from the TradingView homepage bootstrap. Must contain `id`, `username`, `pro_plan`, `is_pro`, `is_broker`. |
| `max_bars` | `int` | Plan-based `max_bars` estimate from `CapabilityDetector`. |
| `tier` | `str` | Normalized tier string from `CapabilityDetector`. |

Returns a `TradingViewAccount` with `max_bars_source="estimate"` and `probe_status="pending"`.

---

## Access Pattern

```python
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV(browser="chrome") as client:
    account = client.account   # TradingViewAccount | None

    if account is None:
        print("Anonymous session — 5,000 bar free-tier limit applies")
    else:
        print(f"Logged in as user_id={account.user_id}")
        print(f"TradingView plan: {account.plan!r}")
        print(f"Tier: {account.tier}")
        print(f"Max bars: {account.max_bars} (source: {account.max_bars_source})")
        print(f"Probe status: {account.probe_status}")
```

`client.account` returns `None` when:

- The session is anonymous (no credentials)
- The session uses direct token injection (`auth_token=...`) — no profile fetch is performed

---

## See Also

- [Concepts: Account Capabilities](../../concepts/capabilities.md)
- [AuthManager Reference](manager.md)
- [TradingViewCredentials Reference](credentials.md)
- [OHLCV Client Reference](../chart/ohlcv.md)
- [TradingView Pricing](https://www.tradingview.com/pricing/)
