# Chart Utilities Reference

**Module:** `tvkit.api.chart.utils`
**Available since:** v0.2.0

Timestamp conversion, interval validation, and range parameter construction utilities used by the OHLCV client. All functions are synchronous.

---

## Import

```python
from tvkit.api.chart.utils import (
    MAX_BARS_REQUEST,
    build_range_param,
    end_of_day_timestamp,
    to_unix_timestamp,
    validate_interval,
)
```

---

## Constants

### `MAX_BARS_REQUEST`

```python
MAX_BARS_REQUEST: int = 5000
```

Sentinel bar count sent to TradingView's `create_series` call during range mode. TradingView ignores this value when a `modify_series` range is active, but the parameter slot must be filled.

The value `5000` is the free-tier conservative limit. Range mode works correctly at all account tiers because the date range constraint (not the bar count) controls data volume.

**Account tier bar limits (intraday intervals):**

| Tier | Bar Limit |
|------|-----------|
| Free / Basic | 5,000 |
| Essential / Plus | 10,000 |
| Premium | 20,000 |
| Expert | 25,000 |
| Ultimate | 40,000 |

Source: TradingView support — "Historical intraday data bars and limits explained."

---

## Functions

### `to_unix_timestamp()`

Convert a datetime or ISO 8601 string to a UTC Unix timestamp (integer seconds).

```python
def to_unix_timestamp(ts: datetime | str) -> int: ...
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ts` | `datetime \| str` | required | A timezone-aware datetime, naive datetime, or ISO 8601 string. Strings with a `"Z"` UTC designator are supported. |

**Returns:** `int` — Unix timestamp in integer seconds since epoch. Sub-second precision is truncated (not rounded).

**Raises:**

| Exception | When |
|-----------|------|
| `TypeError` | `ts` is not a `datetime` or `str` |
| `ValueError` | String cannot be parsed as ISO 8601 |

**Naive datetime behaviour:** Naive datetimes (no `tzinfo`) are **assigned** UTC timezone without any conversion. A datetime representing a local time in another timezone will be silently misinterpreted as UTC. Always supply timezone-aware datetimes for correctness.

**Examples:**

```python
from datetime import datetime, UTC
from tvkit.api.chart.utils import to_unix_timestamp

to_unix_timestamp("2024-01-01")                          # 1704067200
to_unix_timestamp("2024-01-01T00:00:00Z")                # 1704067200
to_unix_timestamp(datetime(2024, 1, 1, tzinfo=UTC))      # 1704067200
to_unix_timestamp("2024-06-15T09:30:00+00:00")           # 1718443800
```

---

### `end_of_day_timestamp()`

Return the Unix timestamp for the **end of the calendar day** (23:59:59 UTC) when the input is a date-only value, or the exact Unix timestamp when a time component is present.

```python
def end_of_day_timestamp(ts: datetime | str) -> int: ...
```

Used internally by `get_historical_ohlcv()` for client-side range filtering to ensure intraday bars on the last requested day are not excluded by a midnight boundary.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ts` | `datetime \| str` | required | Timezone-aware datetime, naive datetime (assigned UTC), or ISO 8601 string. |

**Date-only detection:**

| Input type | Treated as date-only when |
|------------|--------------------------|
| `str` | No space (`" "`) and no `"T"` separator |
| `datetime` | `hour == 0` and `minute == 0` and `second == 0` and `microsecond == 0` |

**Returns:** `int` — Unix timestamp. For date-only inputs, adds 86,399 seconds (23h 59m 59s) to midnight.

**Raises:** Same as `to_unix_timestamp`.

**Examples:**

```python
from tvkit.api.chart.utils import end_of_day_timestamp

end_of_day_timestamp("2025-12-31")           # 1767225599  (2025-12-31 23:59:59 UTC)
end_of_day_timestamp("2025-12-31 16:00")     # 1767196800  (unchanged — time present)
end_of_day_timestamp("2025-12-31T09:30:00")  # 1767199800  (unchanged — time present)
```

---

### `build_range_param()`

Build a TradingView range parameter string from start and end timestamps.

```python
def build_range_param(start: datetime | str, end: datetime | str) -> str: ...
```

The returned string is passed as the last argument of a `modify_series` WebSocket message to constrain the historical data window. TradingView applies the range server-side.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start` | `datetime \| str` | required | Start of the range (inclusive). Accepts timezone-aware datetime, naive datetime (assigned UTC), or ISO 8601 string (including `"Z"` suffix). |
| `end` | `datetime \| str` | required | End of the range (inclusive). Same accepted types as `start`. |

**Returns:** `str` — Range string in the format `"r,{from_unix}:{to_unix}"`.

```
"r,1704067200:1735689600"
```

**Raises:**

| Exception | When |
|-----------|------|
| `TypeError` | `start` or `end` is not a `datetime` or `str` |
| `ValueError` | String cannot be parsed as ISO 8601 |
| `ValueError` | `start > end` (equal values are valid — fetches a single day's bars) |

**Examples:**

```python
from tvkit.api.chart.utils import build_range_param

build_range_param("2024-01-01", "2024-12-31")
# "r,1704067200:1735603200"

build_range_param("2024-06-15", "2024-06-15")   # single day — valid
# "r,1718409600:1718409600"
```

---

### `validate_interval()`

Validate a TradingView interval format string. Raises on invalid input; returns `None` on success.

```python
def validate_interval(interval: str) -> None: ...
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `interval` | `str` | required | TradingView interval string. |

**Valid interval formats:**

| Category | Format | Examples | Range |
|----------|--------|---------|-------|
| Minutes | `{N}` (digits only) | `"1"`, `"5"`, `"15"`, `"30"`, `"1440"` | 1–1440 |
| Seconds | `{N}S` | `"1S"`, `"15S"`, `"30S"` | 1S–60S |
| Hours | `{N}H` | `"1H"`, `"4H"`, `"12H"` | 1H–168H |
| Days | `D` or `{N}D` | `"D"`, `"1D"`, `"3D"` | 1D–365D |
| Weeks | `W` or `{N}W` | `"W"`, `"1W"`, `"4W"` | 1W–52W |
| Months | `M` or `{N}M` | `"M"`, `"1M"`, `"6M"` | 1M–12M |

**Note:** Range limits (e.g. minutes 1–1440, months 1–12) are client-side safety guards. TradingView may accept different ranges server-side. Verify against the TradingView UI if you need an interval outside these bounds.

**Returns:** `None`

**Raises:**

| Exception | When |
|-----------|------|
| `TypeError` | `interval` is not a string |
| `ValueError` | `interval` is an empty string |
| `ValueError` | Format does not match any supported pattern |
| `ValueError` | Numeric value is outside the allowed range for its unit |

**Examples:**

```python
from tvkit.api.chart.utils import validate_interval

validate_interval("5")       # OK — 5 minutes
validate_interval("1H")      # OK — 1 hour
validate_interval("D")       # OK — daily
validate_interval("15S")     # OK — 15 seconds
validate_interval("2W")      # OK — 2 weeks
validate_interval("3M")      # OK — 3 months

validate_interval("invalid")  # raises ValueError
validate_interval("1441")     # raises ValueError — exceeds minute range
validate_interval("13M")      # raises ValueError — exceeds month range
validate_interval(1)          # raises TypeError
```

---

## See Also

- [Historical Data Guide](../../guides/historical-data.md)
- [Concepts: Intervals](../../concepts/intervals.md)
- [OHLCV Client Reference](ohlcv.md)
