# Timezone Handling

[Home](../index.md) > [Concepts](../concepts/index.md) > Timezone Handling

tvkit uses a single, consistent rule for all timestamps:

> **All internal timestamps are UTC. All timezone conversion is explicit and opt-in.**

This document explains what that means, why it was chosen, and how to work with it.

---

## UTC Internal Model

Every `OHLCVBar.timestamp` value is a **UTC Unix epoch float** — seconds since
`1970-01-01T00:00:00Z` (fractional seconds allowed). This is how TradingView sends timestamps over its WebSocket protocol, and
tvkit preserves them exactly as received.

```python
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV() as client:
    bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=3)

for bar in bars:
    print(bar.timestamp)
# 1704067200.0  ← UTC epoch seconds
# 1704153600.0
# 1704240000.0
```

tvkit never stores local time internally. There is no implicit timezone, no locale-dependent
behavior, and no silent conversion.

---

## Timezone Invariant

The library enforces a hard invariant on `OHLCVBar.timestamp`:

> `OHLCVBar.timestamp` MUST always be a UTC Unix epoch float in the range `[0, 7_258_118_400]`
> (1970-01-01 to 2200-01-01).

A Pydantic `field_validator` on `OHLCVBar` rejects any value outside this range with a
`ValueError`. This catches miscoded timestamps (e.g., milliseconds passed as seconds, or a
negative value) at the model boundary rather than silently propagating bad data downstream.

The upper bound intentionally extends well beyond modern market data. Its primary purpose is to
detect milliseconds passed as seconds — for example, `1_704_067_200_000` (a 13-digit ms timestamp)
far exceeds `7_258_118_400` and is rejected immediately.

All conversions — to exchange local time, to a research timezone, or to any other representation —
happen **at the display or analysis boundary**, never in the data layer.

```
Internal data layer         Display / analysis boundary
─────────────────────       ──────────────────────────
OHLCVBar.timestamp          convert_to_timezone(df, "America/New_York")
  float, UTC epoch    ─────►  Polars datetime[us, America/New_York]
  never modified
```

---

## Naive Datetime Handling

When you pass a naive `datetime` (no `tzinfo`) to `get_historical_ohlcv()` or to any `tvkit.time`
function, tvkit assumes it represents UTC and emits a one-time `UserWarning`:

```python
from datetime import datetime
from tvkit.time import to_utc

dt = to_utc(datetime(2024, 6, 1, 9, 30))
# UserWarning: Naive datetime 2024-06-01 09:30:00 assumed UTC.
#              Attach tzinfo=timezone.utc to suppress this warning.
```

To suppress the warning, always pass timezone-aware datetimes:

```python
from datetime import datetime, UTC

dt = datetime(2024, 6, 1, 9, 30, tzinfo=UTC)  # No warning
```

---

## Exchange Timezone Mapping

`exchange_timezone(exchange)` maps a TradingView exchange code to an
[IANA timezone string](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

```python
from tvkit.time import exchange_timezone

exchange_timezone("NASDAQ")   # "America/New_York"
exchange_timezone("SET")      # "Asia/Bangkok"
exchange_timezone("LSE")      # "Europe/London"
exchange_timezone("TSX")      # "America/Toronto"
```

The registry covers all exchanges defined in `tvkit.api.scanner.markets.MARKET_INFO`. The lookup is
layered:

1. **User overrides** — registered via `register_exchange()` or `load_exchange_overrides()`
2. **Built-in registry** — the bundled `_EXCHANGE_TIMEZONES` dict
3. **UTC fallback** — unknown exchange codes fall back to `"UTC"` with a WARNING log (logged once
   per unknown code)

The fallback to UTC rather than raising `ValueError` prevents disruption when TradingView adds new
exchanges before the registry is updated.

---

## Crypto Exchanges = UTC

Crypto exchanges such as `BINANCE`, `COINBASE`, `KRAKEN`, and `BYBIT` are mapped to `"UTC"`.

This is intentional and correct. Crypto markets:

- Trade **24/7** with no market open/close session
- Have no exchange-local time concept (Binance operates globally, not from a single timezone)
- Express all their data in UTC by convention

Converting a BINANCE timestamp to a regional timezone such as `"Asia/Singapore"` would be
**misleading** — there is no meaningful "local session" to anchor the conversion to. UTC is the
right timezone for crypto data.

```python
from tvkit.time import exchange_timezone

exchange_timezone("BINANCE")   # "UTC"
exchange_timezone("COINBASE")  # "UTC"
exchange_timezone("KRAKEN")    # "UTC"
```

---

## Research Timezone Convention

For analysis and visualization, you often want human-readable timestamps in the exchange's local
timezone — so bar times align with market open/close hours.

```python
import asyncio
import polars as pl
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter
from tvkit.time import convert_to_exchange_timezone

async def fetch_and_display() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "60", bars_count=10)

    exporter = DataExporter()
    df = await exporter.to_polars(bars)

    # Convert UTC epoch → America/New_York for display
    df_local = convert_to_exchange_timezone(df, "NASDAQ")
    print(df_local.select(["timestamp", "close"]))
    # timestamp                        close
    # 2024-01-15 09:30:00 EST           185.94
    # 2024-01-15 10:30:00 EST           186.12
    # ...

asyncio.run(fetch_and_display())
```

The function returns a new DataFrame with the converted `timestamp` column. The original DataFrame
is unchanged (Polars immutability).

---

## When NOT to Convert

Do **not** convert timestamps in these contexts:

| Context | Why to keep UTC |
|---------|----------------|
| **Backtesting** | Consistent epoch arithmetic; no DST gaps or ambiguous offsets |
| **ML model training** | Models expect uniform numeric features; local time introduces spurious discontinuities |
| **Cross-dataset joins** | Joining NYSE (`America/New_York`, UTC-5/4) and SET (`Asia/Bangkok`, UTC+7) data in local time requires managing two incompatible offsets; UTC is the common key |
| **Storing to parquet/database** | Store UTC epoch; convert only at query time |

A common mistake is converting early in a pipeline and then joining datasets from different
exchanges — the timestamps no longer align because each exchange has a different UTC offset.

**Rule:** convert late (at the display or report layer), not early.

---

## Design Principles

tvkit's timezone behaviour is guided by three principles:

1. **UTC everywhere internally** — all timestamps in the data layer are UTC Unix epoch floats;
   no local time is ever stored or inferred.
2. **Explicit, opt-in conversion** — timezone conversion never happens automatically; you call
   a conversion function only when you need a human-readable representation.
3. **Convert late in the pipeline** — convert at the display or analysis boundary, not at
   ingestion. Converting early makes cross-dataset joins fragile and introduces DST artifacts
   in backtests and ML features.

These principles apply consistently across equities, crypto, and any other asset class tvkit
supports.

---

## See Also

- [tvkit.time Reference](../reference/time/index.md) — full API documentation for all conversion functions
- [Historical Data Guide — Working with Timezones](../guides/historical-data.md#working-with-timezones) — runnable examples
- [OHLCV Reference — Timezone Behavior](../reference/chart/ohlcv.md#timezone-behavior) — `OHLCVBar.timestamp` contract
- [FAQ — Timezones](../faq.md#timezones) — common questions and answers
