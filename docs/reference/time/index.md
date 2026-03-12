# tvkit.time Reference

**Module:** `tvkit.time`
**Available since:** v0.6.0

UTC timezone utilities for TradingView OHLCV data. All timestamps inside tvkit represent UTC Unix epoch seconds. This module provides utilities for normalizing datetimes to UTC and converting Polars DataFrames or scalar timestamps to any IANA timezone.

---

## Import

```python
from tvkit.time import (
    # Type alias
    TimestampUnit,
    # UTC normalization
    to_utc,
    ensure_utc,
    # Scalar conversion
    convert_timestamp,
    # DataFrame conversion
    convert_to_timezone,
    convert_to_exchange_timezone,
    # Exchange registry
    exchange_timezone,
    exchange_timezone_map,
    supported_exchanges,
    register_exchange,
    load_exchange_overrides,
    validate_exchange_registry,
)
```

---

## Public API

| Symbol | Kind | Description |
|--------|------|-------------|
| `TimestampUnit` | type alias | `Literal["s", "ms"]` — time unit for epoch columns |
| `to_utc` | function | Convert any datetime to UTC; warns once on naive input |
| `ensure_utc` | function | Semantic alias for `to_utc` — use in validation contexts |
| `convert_timestamp` | function | Convert a single UTC epoch float to a tz-aware datetime |
| `convert_to_timezone` | function | Convert a DataFrame epoch column to a tz-aware datetime column |
| `convert_to_exchange_timezone` | function | `convert_to_timezone` using an exchange code to resolve the IANA timezone |
| `exchange_timezone` | function | Look up the IANA timezone for a TradingView exchange code |
| `exchange_timezone_map` | dict | The full built-in exchange → timezone mapping |
| `supported_exchanges` | function | Return all exchange codes in the registry |
| `register_exchange` | function | Add or override an exchange → timezone mapping at runtime |
| `load_exchange_overrides` | function | Load exchange overrides from a YAML file |
| `validate_exchange_registry` | function | Validate that all registry entries are valid IANA timezone strings |

---

## Conversion Flow

```
UTC epoch float (OHLCVBar.timestamp)
        │
        ▼
convert_to_timezone(df, "America/New_York")
        │
        ▼
Polars datetime[us, America/New_York]


OHLCV DataFrame (UTC epoch column)
        │
        ▼
convert_to_exchange_timezone(df, "NYSE")
  └─► exchange_timezone("NYSE") → "America/New_York"
        │
        ▼
Polars datetime[us, America/New_York]


OHLCV DataFrame (UTC epoch column)
        │
        ▼
convert_to_exchange_timezone(df, "BINANCE")
  └─► exchange_timezone("BINANCE") → "UTC"  (crypto = 24/7, no local session)
        │
        ▼
Polars datetime[us, UTC]
```

---

## `TimestampUnit`

```python
TimestampUnit = Literal["s", "ms"]
```

Time unit for epoch-based timestamp columns.

- `"s"` — Unix epoch seconds (default; TradingView OHLCV timestamps)
- `"ms"` — Unix epoch milliseconds (REST APIs, third-party data sources)

---

## `to_utc()`

```python
def to_utc(dt: datetime) -> datetime: ...
```

Convert any `datetime` to UTC.

Naive datetimes are assumed to represent UTC and a one-time `UserWarning` is emitted. Tz-aware datetimes are silently converted to UTC.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `dt` | `datetime` | Any `datetime` object, naive or tz-aware |

### Returns

`datetime` — UTC tz-aware datetime.

### Raises

| Exception | When |
|-----------|------|
| `TypeError` | `dt` is not a `datetime` instance |

### Example

```python
from datetime import datetime, UTC
from tvkit.time import to_utc

# Naive — warns once
utc = to_utc(datetime(2024, 1, 1, 9, 30))
# UserWarning: Naive datetime 2024-01-01 09:30:00 assumed UTC. ...

# Tz-aware — silent
utc = to_utc(datetime(2024, 1, 1, 9, 30, tzinfo=UTC))  # already UTC, returned as-is

# Tz-aware with offset — silently converted
from datetime import timezone, timedelta
jst = timezone(timedelta(hours=9))
utc = to_utc(datetime(2024, 1, 1, 18, 30, tzinfo=jst))  # → 2024-01-01 09:30:00+00:00
```

---

## `ensure_utc()`

```python
def ensure_utc(dt: datetime) -> datetime: ...
```

Semantic alias for `to_utc()`. Use in validation contexts where the intent is "this must be UTC" rather than "convert to UTC." The behavior is identical.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `dt` | `datetime` | Any `datetime` object, naive or tz-aware |

### Returns

`datetime` — UTC tz-aware datetime.

### Raises

| Exception | When |
|-----------|------|
| `TypeError` | `dt` is not a `datetime` instance |

---

## `convert_timestamp()`

```python
def convert_timestamp(ts: float, tz: str) -> datetime: ...
```

Convert a UTC Unix epoch float to a tz-aware datetime in the target timezone. Useful for single-value conversion outside a DataFrame context.

The conversion is always UTC-first: `epoch → UTC datetime → target timezone`.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `ts` | `float` | UTC Unix epoch seconds |
| `tz` | `str` | IANA timezone string (e.g. `"Asia/Bangkok"`, `"America/New_York"`) |

### Returns

`datetime` — tz-aware datetime in the specified timezone.

### Raises

| Exception | When |
|-----------|------|
| `ZoneInfoNotFoundError` | `tz` is not a valid IANA timezone string |

### Example

```python
from tvkit.time import convert_timestamp

dt = convert_timestamp(1_700_000_000, "Asia/Bangkok")
print(dt)  # 2023-11-15 06:13:20+07:00

dt = convert_timestamp(1_704_067_200, "America/New_York")
print(dt)  # 2024-01-01 00:00:00-05:00
```

---

## `convert_to_timezone()`

```python
def convert_to_timezone(
    df: pl.DataFrame,
    tz: str,
    column: str = "timestamp",
    unit: TimestampUnit = "s",
) -> pl.DataFrame: ...
```

Convert an epoch numeric column in a Polars DataFrame to a tz-aware datetime column.

The column is replaced in the returned DataFrame. The original DataFrame is not mutated (Polars `with_columns` immutability).

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `df` | `pl.DataFrame` | required | DataFrame containing the epoch column |
| `tz` | `str` | required | IANA timezone string |
| `column` | `str` | `"timestamp"` | Name of the epoch column to convert |
| `unit` | `TimestampUnit` | `"s"` | Time unit: `"s"` for seconds, `"ms"` for milliseconds |

### Returns

`pl.DataFrame` — New DataFrame with the named column replaced by a tz-aware Polars datetime column.

### Raises

| Exception | When |
|-----------|------|
| `ZoneInfoNotFoundError` | `tz` is not a valid IANA timezone string |
| `ColumnNotFoundError` | `column` is not present in `df` |

### Example

```python
import polars as pl
from tvkit.time import convert_to_timezone

# TradingView timestamps are seconds (default unit="s")
df_ny = convert_to_timezone(df, "America/New_York")

# Third-party data in milliseconds
df_ms = convert_to_timezone(df_ms, "UTC", unit="ms")

# Non-default column name
df_bkk = convert_to_timezone(df, "Asia/Bangkok", column="open_time")
```

---

## `convert_to_exchange_timezone()`

```python
def convert_to_exchange_timezone(
    df: pl.DataFrame,
    exchange: str,
    column: str = "timestamp",
    unit: TimestampUnit = "s",
) -> pl.DataFrame: ...
```

Convert the epoch column to the exchange's local timezone. Thin wrapper that resolves the exchange code to an IANA timezone via `exchange_timezone()`, then delegates to `convert_to_timezone()`.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `df` | `pl.DataFrame` | required | DataFrame containing the epoch column |
| `exchange` | `str` | required | TradingView exchange code (e.g. `"NASDAQ"`, `"SET"`, `"BINANCE"`) or full symbol string (e.g. `"NASDAQ:AAPL"`). Case-insensitive. |
| `column` | `str` | `"timestamp"` | Name of the epoch column to convert |
| `unit` | `TimestampUnit` | `"s"` | Time unit: `"s"` for seconds, `"ms"` for milliseconds |

### Returns

`pl.DataFrame` — New DataFrame with the named column replaced by a tz-aware datetime column in the exchange's local timezone.

### Notes

- Unknown exchange codes fall back to UTC with a WARNING log (logged once per unique unknown code)
- Crypto exchanges (`BINANCE`, `COINBASE`, `KRAKEN`, `BYBIT`, etc.) map to `"UTC"` — they operate 24/7 with no market session and no concept of exchange-local time
- Full symbol strings like `"NASDAQ:AAPL"` are supported — the exchange prefix is extracted automatically

### Example

```python
from tvkit.time import convert_to_exchange_timezone

df_ny  = convert_to_exchange_timezone(df, "NASDAQ")    # America/New_York
df_bkk = convert_to_exchange_timezone(df, "SET")       # Asia/Bangkok
df_utc = convert_to_exchange_timezone(df, "BINANCE")   # UTC (crypto, 24/7)

# Also accepts a full symbol string
df_ny  = convert_to_exchange_timezone(df, "NASDAQ:AAPL")  # extracts "NASDAQ"
```

---

## `exchange_timezone()`

```python
def exchange_timezone(exchange: str) -> str: ...
```

Look up the IANA timezone string for a TradingView exchange code.

The lookup is layered: user overrides → built-in registry → UTC fallback.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `exchange` | `str` | TradingView exchange code or full `EXCHANGE:SYMBOL` string. Case-insensitive. |

### Returns

`str` — IANA timezone string (e.g. `"America/New_York"`). Returns `"UTC"` for unknown codes (with a one-time WARNING log).

### Example

```python
from tvkit.time import exchange_timezone

exchange_timezone("NASDAQ")       # "America/New_York"
exchange_timezone("SET")          # "Asia/Bangkok"
exchange_timezone("LSE")          # "Europe/London"
exchange_timezone("BINANCE")      # "UTC"
exchange_timezone("UNKNOWN_EX")   # "UTC"  + WARNING logged once
exchange_timezone("NASDAQ:AAPL")  # "America/New_York"  (symbol string accepted)
```

---

## `exchange_timezone_map`

```python
exchange_timezone_map: dict[str, str]
```

The full built-in exchange → IANA timezone mapping. Covers all 69 exchanges in `tvkit.api.scanner.markets.MARKET_INFO`. Read-only reference; modify via `register_exchange()` or `load_exchange_overrides()`.

---

## `supported_exchanges()`

```python
def supported_exchanges() -> list[str]: ...
```

Return all exchange codes currently in the registry (built-in + user overrides).

### Returns

`list[str]` — Sorted list of uppercase exchange codes.

---

## `register_exchange()`

```python
def register_exchange(exchange: str, tz: str) -> None: ...
```

Add or override an exchange → IANA timezone mapping at runtime. Useful for custom data sources, internal exchange codes, or testing.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `exchange` | `str` | Exchange code (case-insensitive; stored as uppercase) |
| `tz` | `str` | IANA timezone string |

### Raises

| Exception | When |
|-----------|------|
| `ZoneInfoNotFoundError` | `tz` is not a valid IANA timezone string |

### Example

```python
from tvkit.time import register_exchange, exchange_timezone

register_exchange("MYEX", "Asia/Kolkata")
exchange_timezone("MYEX")  # "Asia/Kolkata"
```

---

## `load_exchange_overrides()`

```python
def load_exchange_overrides(path: str | Path | None = None) -> None: ...
```

Load exchange → IANA timezone overrides from a YAML file. If `path` is `None`, the function checks the `TVKIT_EXCHANGE_OVERRIDES` environment variable for a file path. If neither is provided, the function is a no-op.

### YAML Format

```yaml
MYEX: Asia/Kolkata
CUSTOM: America/Chicago
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str \| Path \| None` | `None` | Path to a YAML file, or `None` to use the `TVKIT_EXCHANGE_OVERRIDES` environment variable |

### Raises

| Exception | When |
|-----------|------|
| `FileNotFoundError` | Path is provided but the file does not exist |
| `ZoneInfoNotFoundError` | A timezone value in the YAML is not a valid IANA string |

---

## `validate_exchange_registry()`

```python
def validate_exchange_registry() -> list[str]: ...
```

Validate that all entries in the built-in registry are valid IANA timezone strings. Returns a list of exchange codes whose timezone values failed validation. An empty list means all entries are valid.

### Returns

`list[str]` — Exchange codes with invalid timezone strings. Empty list if all are valid.

### Example

```python
from tvkit.time import validate_exchange_registry

errors = validate_exchange_registry()
if errors:
    print(f"Invalid timezone entries: {errors}")
```

---

## See Also

- [Concepts: Timezones](../../concepts/timezones.md) — design rationale, UTC invariant, when NOT to convert
- [Historical Data Guide — Working with Timezones](../../guides/historical-data.md#working-with-timezones) — runnable examples
- [OHLCV Reference — Timezone Behavior](../chart/ohlcv.md#timezone-behavior) — `OHLCVBar.timestamp` contract
- [FAQ — Timezones](../../faq.md#timezones) — common questions and answers
