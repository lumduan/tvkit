# OHLCV Client Reference

**Module:** `tvkit.api.chart.ohlcv`
**Available since:** v0.1.0

Async WebSocket client for streaming real-time and historical OHLCV data from TradingView. All methods validate symbols and intervals before opening a connection.

---

## Import

```python
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.chart import Adjustment          # price adjustment mode enum
```

---

## `OHLCV`

Async context manager that manages a TradingView WebSocket connection. Each method call opens a fresh connection and closes it on completion (or on context manager exit).

Supports optional account authentication. Pass `browser`, `cookies`, or `auth_token` (as keyword arguments) to use an authenticated session. When no credential is provided, the session runs in anonymous mode with a 5,000-bar limit. See [Authenticated Sessions Guide](../../guides/authenticated-sessions.md) for full details.

### Signature

```python
class OHLCV:
    def __init__(
        self,
        max_attempts: int = 5,
        base_backoff: float = 1.0,
        max_backoff: float = 30.0,
        *,
        browser: str | None = None,
        browser_profile: str | None = None,
        cookies: dict[str, str] | None = None,
        auth_token: str | None = None,
    ) -> None: ...
```

### Constructor Parameters

**Reconnection parameters** (positional, optional):

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_attempts` | `int` | `5` | Total WebSocket connection attempts before raising `StreamConnectionError`. |
| `base_backoff` | `float` | `1.0` | Base retry delay in seconds. Doubles each attempt. |
| `max_backoff` | `float` | `30.0` | Maximum retry delay cap in seconds. |

**Authentication parameters** (keyword-only, optional):

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `browser` | `str \| None` | `None` | Browser to extract session cookies from. Must be `"chrome"` or `"firefox"`. Mutually exclusive with `cookies` and `auth_token`. When `None` and no other credential kwarg is provided, `TVKIT_BROWSER` env var is used as fallback. |
| `browser_profile` | `str \| None` | `None` | Specific browser profile name (e.g. `"Default"`, `"Profile 2"`). Only valid when `browser` resolves to a value. |
| `cookies` | `dict[str, str] \| None` | `None` | Pre-extracted cookie dict. Mutually exclusive with `browser` and `auth_token`. |
| `auth_token` | `str \| None` | `None` | Pre-obtained TradingView auth token. Mutually exclusive with `browser` and `cookies`. When `None` and no other credential kwarg is provided, `TVKIT_AUTH_TOKEN` env var is used as fallback. |

**Credential resolution order:** constructor kwargs → `TVKIT_BROWSER` / `TVKIT_AUTH_TOKEN` env vars → anonymous mode. Providing conflicting sources (e.g. both `browser` kwarg and `TVKIT_AUTH_TOKEN` env var, or both `TVKIT_BROWSER` and `TVKIT_AUTH_TOKEN`) raises `ValueError` at construction.

### Context Manager Usage

```python
# Anonymous session (unchanged from pre-v0.7.0)
async with OHLCV() as client:
    bars = await client.get_historical_ohlcv(
        exchange_symbol="NASDAQ:AAPL",
        interval="1D",
        bars_count=10,
    )

# Authenticated session via Chrome cookies
async with OHLCV(browser="chrome") as client:
    bars = await client.get_historical_ohlcv(
        exchange_symbol="NASDAQ:AAPL",
        interval="1D",
        bars_count=10_000,
    )
```

`OHLCV` implements `__aenter__` and `__aexit__`. The `__aexit__` method cancels any background capability probe task and closes the active WebSocket connection. It is safe to call multiple methods on the same client instance sequentially — each method call re-establishes the connection.

---

## Properties

### `account`

```python
@property
def account(self) -> TradingViewAccount | None: ...
```

The authenticated account profile, or `None`.

Returns `None` when:

- Called before `__aenter__` or after `__aexit__`
- The session is anonymous (no credentials provided and no env vars set)
- The session uses direct token injection (`auth_token=...`) — no profile fetch is performed in this mode

Populated after `__aenter__` for browser and cookie-dict modes with the account tier, `max_bars`, and probe status. The `max_bars` field starts as a plan-based estimate and is updated in-place by the background probe when it completes.

```python
from tvkit.auth import TradingViewAccount

async with OHLCV(browser="chrome") as client:
    account: TradingViewAccount | None = client.account
    if account is not None:
        print(f"Tier: {account.tier!r}, max_bars: {account.max_bars}")
```

See [TradingViewAccount Reference](../auth/account.md) for the full field list.

---

## Methods

### `wait_until_ready()`

```python
async def wait_until_ready(self) -> None: ...
```

Wait until the background capability probe completes.

Returns immediately if:

- No probe is running (anonymous session or direct token injection)
- The probe already finished (success or failure)
- Called before `__aenter__`

Probe failures and probe-task cancellations are treated as non-fatal — the method returns silently in both cases and the plan-based estimate remains in effect. Caller-task cancellation is re-raised so cooperative cancellation is preserved.

#### When to use

Use `wait_until_ready()` when you need probe-confirmed `max_bars` before your first fetch — typically for very large bar counts near the account limit.

#### Example

```python
async with OHLCV(browser="chrome") as client:
    await client.wait_until_ready()
    account = client.account
    if account:
        print(f"max_bars confirmed: {account.max_bars} (source={account.max_bars_source!r})")
    bars = await client.get_historical_ohlcv(
        exchange_symbol="NASDAQ:AAPL",
        interval="1",
        bars_count=50_000,
    )
```

See [Concepts: Account Capabilities — wait_until_ready()](../../concepts/capabilities.md#wait_until_ready) for the full trade-off discussion.

---

### `get_historical_ohlcv()`

Fetch a list of historical OHLCV bars. Supports two mutually exclusive modes: **count mode** (most recent N bars) and **range mode** (all bars within a date window).

```python
async def get_historical_ohlcv(
    self,
    exchange_symbol: str,
    interval: str = "1",
    bars_count: int | None = None,
    *,
    start: datetime | str | None = None,
    end: datetime | str | None = None,
    adjustment: Adjustment = Adjustment.SPLITS,
) -> list[OHLCVBar]: ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `exchange_symbol` | `str` | required | Symbol in `EXCHANGE:SYMBOL` or `EXCHANGE-SYMBOL` format. Dash format is auto-converted. |
| `interval` | `str` | `"1"` | TradingView interval string. See [Intervals](../../concepts/intervals.md) for valid values. |
| `bars_count` | `int \| None` | `None` | Count mode: number of most-recent bars to fetch. Mutually exclusive with `start`/`end`. Must be a positive integer. No implicit default — must be provided explicitly in count mode. |
| `start` | `datetime \| str \| None` | `None` | Range mode: start of date window (inclusive). Keyword-only. Accepts timezone-aware datetime, naive datetime (assigned UTC), or ISO 8601 string. Must be used together with `end`. |
| `end` | `datetime \| str \| None` | `None` | Range mode: end of date window (inclusive). Keyword-only. Same accepted types as `start`. Must be used together with `start`. |
| `adjustment` | `Adjustment` | `Adjustment.SPLITS` | Price adjustment mode. Keyword-only. `Adjustment.SPLITS` (default) — split-adjusted only, identical to pre-v0.11.0 behaviour. `Adjustment.DIVIDENDS` — dividend-adjusted (total-return) prices; all prior bars are backward-adjusted for cash dividends. A raw string `"splits"` or `"dividends"` is accepted and coerced automatically. An unknown string raises `ValueError` before any network I/O. |

#### Mode Selection

| Provided | Mode |
|----------|------|
| `bars_count` only | Count mode — fetches N most recent bars |
| `start` + `end` only | Range mode — fetches all bars in the date window |
| Neither | Raises `ValueError` |
| Both | Raises `ValueError` |
| Only `start` or only `end` | Raises `ValueError` |

#### Timeouts

| Mode | Timeout |
|------|---------|
| Count mode | 30 seconds |
| Range mode | 180 seconds |

Range mode uses a longer timeout because multi-year intraday streams can be slow to transmit.

#### Automatic Segmentation (v0.5.0+)

When the estimated bar count for a `start`/`end` range exceeds the per-segment limit, `get_historical_ohlcv()` automatically dispatches to `SegmentedFetchService`, which:

1. Splits the range into non-overlapping segments sized for at most `max_bars` bars each
2. Fetches each segment sequentially via the internal `_fetch_single_range()` method
3. Merges, deduplicates by timestamp (first-occurrence wins), and sorts results chronologically

The caller sees no difference — the return type is the same `list[OHLCVBar]`.

**Segment size depends on the session type:**

| Session | Segment size |
| ------- | ------------ |
| Anonymous | `MAX_BARS_REQUEST` (5,000) |
| Authenticated (browser / cookie-dict) | `account.max_bars` — plan estimate or probe-confirmed value |
| Authenticated (direct token) | `MAX_BARS_REQUEST` (5,000) — no plan info available |

The segment size is snapshotted once at the start of each fetch so that a mid-flight probe update cannot change boundaries during a running request. Use `wait_until_ready()` before a large fetch if you want probe-confirmed `max_bars` to be the segment size from the first request.

**Constraints:**

- Monthly (`M`, `1M`, …) and weekly (`W`, `1W`, …) intervals are never segmented — they always use a single request
- If the range requires more than `MAX_SEGMENTS` (2,000) segments, `RangeTooLargeError` is raised before any fetch begins. Narrow the date range or use a wider interval
- Segments covering periods with no data (weekends, holidays) are silently skipped (treated as empty, not an error)
- TradingView historical depth limits still apply — see [TradingView Historical Depth Limitation](../../limitations.md)

#### Returns

`list[OHLCVBar]` — Bars sorted by timestamp in ascending order. Returns are never empty; `RuntimeError` is raised if no bars are received.

#### Raises

| Exception | When |
|-----------|------|
| `ValueError` | Neither `bars_count` nor `start`/`end` provided |
| `ValueError` | Both `bars_count` and `start`/`end` provided |
| `ValueError` | Only one of `start`/`end` provided |
| `ValueError` | `bars_count <= 0` |
| `ValueError` | `start > end` |
| `ValueError` | `adjustment` string is not a recognised value (raised before any network I/O) |
| `ValueError` | Symbol format is invalid (from `validate_symbols`) |
| `ValueError` | Interval format is invalid (from `validate_interval`) |
| `ValueError` | TradingView returns a `series_error` (invalid symbol/interval for the requested timeframe) |
| `RuntimeError` | No bars received from TradingView |
| `RangeTooLargeError` | Date range would require more than `MAX_SEGMENTS` (2,000) segments — narrow the range or use a wider interval. Subclass of `ValueError`. |
| `SegmentedFetchError` | A segment fetch failed with an unexpected error. Carries `segment_index`, `segment_start`, `segment_end`, `total_segments`, `cause`. |

#### Examples

**Count mode:**

```python
async with OHLCV() as client:
    bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=100)
print(f"Received {len(bars)} bars. Last close: {bars[-1].close}")
```

**Range mode:**

```python
async with OHLCV() as client:
    bars = await client.get_historical_ohlcv(
        "BINANCE:BTCUSDT",
        "60",
        start="2024-01-01",
        end="2024-03-31",
    )
print(f"Q1 2024: {len(bars)} 1H bars")
```

**With datetime objects:**

```python
from datetime import datetime, UTC

async with OHLCV() as client:
    bars = await client.get_historical_ohlcv(
        "INDEX:NDFI",
        "1D",
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 12, 31, tzinfo=UTC),
    )
```

**Dividend-adjusted prices (count mode):**

```python
from tvkit.api.chart import OHLCV, Adjustment

async with OHLCV() as client:
    # Default — split-adjusted only; identical to all pre-v0.11.0 calls
    splits_bars = await client.get_historical_ohlcv(
        "SET:ADVANC", "1D", bars_count=300,
        adjustment=Adjustment.SPLITS,
    )

    # Dividend-adjusted total-return prices
    div_bars = await client.get_historical_ohlcv(
        "SET:ADVANC", "1D", bars_count=300,
        adjustment=Adjustment.DIVIDENDS,
    )

# Closing prices differ: dividend-adjusted bars are backward-adjusted for cash payouts
print(splits_bars[-1].close)   # e.g. 280.0
print(div_bars[-1].close)      # e.g. 254.9  (lower — dividends deducted from history)
```

**Dividend-adjusted prices (range mode):**

```python
async with OHLCV() as client:
    bars = await client.get_historical_ohlcv(
        "SET:ADVANC", "1D",
        start="2025-01-01", end="2025-12-31",
        adjustment=Adjustment.DIVIDENDS,
    )
```

**Raw string coercion (both forms are equivalent):**

```python
# Enum form — preferred, IDE-autocomplete-friendly
bars = await client.get_historical_ohlcv("SET:ADVANC", "1D", bars_count=5,
                                          adjustment=Adjustment.DIVIDENDS)

# String form — accepted and coerced silently
bars = await client.get_historical_ohlcv("SET:ADVANC", "1D", bars_count=5,
                                          adjustment="dividends")  # type: ignore[arg-type]
```

---

### `get_ohlcv()`

Stream real-time OHLCV bars as an async generator. Yields bars continuously as TradingView pushes updates. The generator runs indefinitely until the caller breaks or the connection drops.

```python
async def get_ohlcv(
    self,
    exchange_symbol: str,
    interval: str = "1",
    bars_count: int = 10,
) -> AsyncGenerator[OHLCVBar, None]: ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `exchange_symbol` | `str` | required | Symbol in `EXCHANGE:SYMBOL` or `EXCHANGE-SYMBOL` format. |
| `interval` | `str` | `"1"` | TradingView interval string (default: 1 minute). |
| `bars_count` | `int` | `10` | Number of historical bars to seed the session with before streaming begins. |

#### Returns

`AsyncGenerator[OHLCVBar, None]` — Yields `OHLCVBar` objects continuously.

#### Raises

| Exception | When |
|-----------|------|
| `ValueError` | Symbol or interval is invalid |
| `ValueError` | TradingView returns a `series_error` |

#### Example

```python
async with OHLCV() as client:
    async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="5", bars_count=50):
        print(f"{bar.timestamp}: close={bar.close} volume={bar.volume}")
        if some_exit_condition:
            break
```

---

### `get_quote_data()`

Stream real-time quote data (current price, status, etc.) as an async generator. Useful for symbols that provide quote data but may not have OHLCV chart data.

```python
async def get_quote_data(
    self,
    exchange_symbol: str,
    interval: str = "1",
    bars_count: int = 10,
) -> AsyncGenerator[QuoteSymbolData, None]: ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `exchange_symbol` | `str` | required | Symbol in `EXCHANGE:SYMBOL` or `EXCHANGE-SYMBOL` format. |
| `interval` | `str` | `"1"` | Chart interval for session setup. |
| `bars_count` | `int` | `10` | Number of seed bars for the session. |

#### Returns

`AsyncGenerator[QuoteSymbolData, None]` — Yields `QuoteSymbolData` objects.

#### Raises

| Exception | When |
|-----------|------|
| `ValueError` | Symbol or interval is invalid |
| `ValueError` | TradingView returns a `series_error` |

#### Example

```python
async with OHLCV() as client:
    async for quote in client.get_quote_data("NASDAQ:AAPL", interval="1"):
        if quote.current_price is not None:
            print(f"Current price: {quote.current_price}")
        break
```

---

### `get_ohlcv_raw()`

Stream raw TradingView WebSocket message dictionaries. Use this for debugging or implementing custom message parsing.

```python
async def get_ohlcv_raw(
    self,
    exchange_symbol: str,
    interval: str = "1",
    bars_count: int = 10,
) -> AsyncGenerator[dict[str, Any], None]: ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `exchange_symbol` | `str` | required | Symbol in `EXCHANGE:SYMBOL` or `EXCHANGE-SYMBOL` format. |
| `interval` | `str` | `"1"` | Chart interval. |
| `bars_count` | `int` | `10` | Number of seed bars. |

#### Returns

`AsyncGenerator[dict[str, Any], None]` — Yields raw parsed JSON dictionaries from TradingView.

#### Raises

| Exception | When |
|-----------|------|
| `ValueError` | Symbol or interval is invalid |

#### Example

```python
async with OHLCV() as client:
    async for raw in client.get_ohlcv_raw("NASDAQ:AAPL", interval="1D"):
        print(raw)  # Raw TradingView message dict
        break
```

---

### `get_latest_trade_info()`

Monitor multiple symbols simultaneously and stream raw trade info messages. Returns raw protocol dicts — parse `"qsd"` messages for price updates.

```python
async def get_latest_trade_info(
    self,
    exchange_symbol: list[str],
) -> AsyncGenerator[dict[str, Any], None]: ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `exchange_symbol` | `list[str]` | required | List of symbols in `EXCHANGE:SYMBOL` or `EXCHANGE-SYMBOL` format. |

#### Returns

`AsyncGenerator[dict[str, Any], None]` — Yields raw TradingView protocol message dicts. Messages of type `"qsd"` contain per-symbol price updates.

#### Raises

| Exception | When |
|-----------|------|
| `ValueError` | Any symbol in the list is invalid |
| `RuntimeError` | Services fail to initialize |

#### Example

```python
symbols = ["NASDAQ:AAPL", "BINANCE:BTCUSDT", "USI:PCC"]

async with OHLCV() as client:
    async for msg in client.get_latest_trade_info(symbols):
        if msg.get("m") == "qsd":
            payload = msg.get("p", [])
            if len(payload) >= 2:
                symbol_data = payload[1]
                print(f"Update: {symbol_data}")
        break
```

---

## Type Definitions

### `OHLCVBar`

```python
from tvkit.api.chart.models.ohlcv import OHLCVBar
```

Represents one OHLCV candlestick bar.

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `float` | UTC Unix epoch seconds for the bar open time |
| `open` | `float` | Opening price |
| `high` | `float` | Highest price during the period |
| `low` | `float` | Lowest price during the period |
| `close` | `float` | Closing price |
| `volume` | `float` | Total volume traded |

#### Timezone Behavior

`OHLCVBar.timestamp` is always a **UTC Unix epoch float**. tvkit never stores local time
internally; timezone conversion is explicit and opt-in at the display or analysis boundary.

A Pydantic `field_validator` rejects timestamps outside `[0, 7_258_118_400]`
(1970-01-01 to 2200-01-01). Values outside this range indicate a unit mismatch (e.g., milliseconds
passed where seconds are expected) or corrupt data, and are rejected with `ValueError` at model
construction time.

**Converting to a target timezone:**

```python
from tvkit.time import convert_to_timezone, convert_to_exchange_timezone

# Convert to any IANA timezone
df_ny = convert_to_timezone(df, "America/New_York")

# Convert using the exchange code (resolves to the exchange's IANA timezone)
df_bkk = convert_to_exchange_timezone(df, "SET")    # Asia/Bangkok
df_utc = convert_to_exchange_timezone(df, "BINANCE") # UTC (crypto, 24/7)
```

See [Concepts: Timezones](../../concepts/timezones.md) for the full explanation, and
[tvkit.time Reference](../time/index.md) for the complete API.

### `Adjustment`

```python
from tvkit.api.chart import Adjustment
```

`StrEnum` controlling the price adjustment mode applied to historical OHLCV bars. Maps directly to the `adjustment` field in TradingView's `resolve_symbol` WebSocket message.

| Member | Value | Description |
|--------|-------|-------------|
| `Adjustment.SPLITS` | `"splits"` | Split-adjusted prices only. **Default.** Identical to all pre-v0.11.0 behaviour. |
| `Adjustment.DIVIDENDS` | `"dividends"` | Dividend-adjusted (total-return) prices. Every prior bar is backward-adjusted so that each cash dividend payment is deducted from all earlier closing prices. Use for long-term backtesting of dividend-paying stocks. |

Because `Adjustment` is a `str` enum, members compare equal to their string values:

```python
assert Adjustment.SPLITS == "splits"
assert Adjustment.DIVIDENDS == "dividends"
```

`get_historical_ohlcv()` also accepts raw strings and coerces them automatically — a string that does not match a known member raises `ValueError` before any network I/O.

**Added in v0.11.0.** `Adjustment.NONE` (raw unadjusted prices) is not yet supported — protocol value not confirmed; tracked for a future release.

---

### `QuoteSymbolData`

Returned by `get_quote_data()`. Contains real-time quote fields. The `current_price` field is the most commonly accessed attribute.

| Field | Type | Description |
|-------|------|-------------|
| `current_price` | `float \| None` | Current market price, if available |
| `symbol_info` | `dict` | Raw symbol metadata from TradingView |

---

## Symbol Format

All methods accept symbols in two formats:

| Format | Example | Notes |
|--------|---------|-------|
| `EXCHANGE:SYMBOL` | `NASDAQ:AAPL` | Preferred format |
| `EXCHANGE-SYMBOL` | `USI-PCC` | Auto-converted to colon format |

Symbols are validated asynchronously via `validate_symbols()` before each request. An invalid symbol raises `ValueError: Invalid exchange or symbol or index`.

---

## See Also

- [Historical Data Guide](../../guides/historical-data.md)
- [Real-time Streaming Guide](../../guides/realtime-streaming.md)
- [Macro Indicators Guide](../../guides/macro-indicators.md)
- [Concepts: Symbols](../../concepts/symbols.md)
- [Concepts: Intervals](../../concepts/intervals.md)
- [Concepts: Streaming vs Historical](../../concepts/streaming-vs-historical.md)
- [Chart Utilities Reference](utils.md)
