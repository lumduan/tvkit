# Symbol Normalization

[Home](../index.md) > Guides > Symbol Normalization

`tvkit.symbols` converts any TradingView instrument reference into a single canonical form —
`EXCHANGE:SYMBOL` (uppercase, colon-separated) — before the symbol touches any network call.
This guide walks through the common workflows.

---

## Why normalization exists

TradingView instruments appear in many string representations across user code, data files,
and environment variables. Without a normalization layer:

- Cache keys diverge: `NASDAQ:AAPL` and `nasdaq:aapl` refer to the same instrument but hash
  differently
- `validate_symbols("nasdaq:aapl")` sends a lowercased string to TradingView's HTTP endpoint,
  which may succeed or fail depending on server-side handling
- Batch download deduplication fails silently when the same symbol appears in multiple formats

`tvkit.symbols` resolves all variants in one pass — before any I/O — so every downstream
call always receives a consistent, well-formed string.

---

## Quick start

```python
from tvkit.symbols import normalize_symbol, SymbolNormalizationError

canonical = normalize_symbol("nasdaq:aapl")   # → "NASDAQ:AAPL"
canonical = normalize_symbol("NASDAQ-AAPL")   # → "NASDAQ:AAPL"
canonical = normalize_symbol("NASDAQ:AAPL")   # → "NASDAQ:AAPL" (no-op)
```

`normalize_symbol` is synchronous and raises `SymbolNormalizationError` for inputs that
cannot be resolved to a valid `EXCHANGE:SYMBOL`.

---

## Supported input formats

| Input | Canonical output | Transformation |
|-------|-----------------|---------------|
| `NASDAQ:AAPL` | `NASDAQ:AAPL` | none (already canonical) |
| `nasdaq:aapl` | `NASDAQ:AAPL` | uppercase |
| `NASDAQ-AAPL` | `NASDAQ:AAPL` | dash → colon |
| `nasdaq-aapl` | `NASDAQ:AAPL` | uppercase + dash → colon |
| `BINANCE:btcusdt` | `BINANCE:BTCUSDT` | uppercase |
| `FX_IDC:eurusd` | `FX_IDC:EURUSD` | uppercase |
| `NYSE:BRK.B` | `NYSE:BRK.B` | none |
| `CME_MINI:ES1!` | `CME_MINI:ES1!` | none |

Symbols with leading or trailing whitespace are stripped before processing.

---

## Bare-ticker resolution

Symbols without an exchange prefix (e.g. `AAPL`) cannot be normalized without additional
context. Provide a `default_exchange` via `NormalizationConfig`:

```python
from tvkit.symbols import normalize_symbol, NormalizationConfig

config = NormalizationConfig(default_exchange="NASDAQ")
normalize_symbol("AAPL", config=config)   # → "NASDAQ:AAPL"
normalize_symbol("aapl", config=config)   # → "NASDAQ:AAPL"
```

Exchange-aware symbols are never overridden by `default_exchange`:

```python
normalize_symbol("BINANCE:BTCUSDT", config=config)   # → "BINANCE:BTCUSDT"
```

### Via environment variable

Set `TVKIT_DEFAULT_EXCHANGE` before constructing `NormalizationConfig`:

```bash
export TVKIT_DEFAULT_EXCHANGE=NASDAQ
```

```python
config = NormalizationConfig()            # reads TVKIT_DEFAULT_EXCHANGE at construction time
normalize_symbol("AAPL", config=config)   # → "NASDAQ:AAPL"
```

> **Recommendation:** Pass an explicit `config` object in library code for predictable
> behaviour. Reserve env var reading for application entry points and scripts.

---

## OHLCV integration

As of Phase 3, all `OHLCV` client methods normalize symbols internally before validation.
Lowercased symbols, dash-format symbols, and whitespace-padded inputs are all accepted:

```python
import asyncio
from tvkit.api.chart import OHLCV

async def main() -> None:
    async with OHLCV() as client:
        # All three are equivalent — normalization happens inside the client
        bars = await client.get_historical_ohlcv("nasdaq:aapl", "1D", 100)
        bars = await client.get_historical_ohlcv("NASDAQ-AAPL", "1D", 100)
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", 100)

asyncio.run(main())
```

The internal call ordering inside each `OHLCV` method is:

```python
canonical: str = normalize_symbol(exchange_symbol)   # pure-string, zero I/O
await validate_symbols(canonical)                    # always receives canonical form
```

If you are building a wrapper or pipeline that pre-processes symbols before passing them to
the client, call `normalize_symbol` explicitly before any I/O:

```python
from tvkit.symbols import normalize_symbol, SymbolNormalizationError
from tvkit.api.utils import validate_symbols

async def fetch_with_normalization(raw_symbol: str) -> None:
    try:
        canonical = normalize_symbol(raw_symbol)
    except SymbolNormalizationError as exc:
        # Format error — raised before any network call
        raise ValueError(f"Invalid symbol format: {exc}") from exc

    await validate_symbols(canonical)   # existence check
    # proceed with canonical symbol ...
```

---

## Batch normalization

`normalize_symbols` normalizes a list of symbols in one call. Output order matches input
order; the function raises on the first invalid element.

```python
from tvkit.symbols import normalize_symbols

canonicals = normalize_symbols(["NASDAQ:AAPL", "binance:btcusdt", "nyse-jpm"])
# → ["NASDAQ:AAPL", "BINANCE:BTCUSDT", "NYSE:JPM"]
```

Passing a plain `str` instead of a `list` raises `SymbolNormalizationError` immediately to
prevent silent character-by-character iteration.

---

## Detailed result

Use `normalize_symbol_detailed` when you need to inspect how a symbol was transformed — for
example, in audit logging or pipeline tracing:

```python
from tvkit.symbols import normalize_symbol_detailed, NormalizationType

result = normalize_symbol_detailed("NASDAQ-AAPL")
result.canonical          # "NASDAQ:AAPL"
result.exchange           # "NASDAQ"
result.ticker             # "AAPL"
result.original           # "NASDAQ-AAPL"
result.normalization_type # NormalizationType.DASH_TO_COLON
```

The `normalization_type` field records the highest-priority transformation applied:

| Priority | Type | Condition |
|----------|------|-----------|
| 1 | `WHITESPACE_STRIP` | Input had leading or trailing whitespace |
| 2 | `DEFAULT_EXCHANGE` | Exchange prefix supplied via `default_exchange` |
| 3 | `DASH_TO_COLON` | Dash replaced with colon |
| 4 | `UPPERCASE_ONLY` | Only case-folding applied |
| 5 | `ALREADY_CANONICAL` | No change needed |

For most call sites, `normalize_symbol` returning a plain `str` is preferred.

---

## Error handling

`SymbolNormalizationError` (a subclass of `ValueError`) is raised for any input that cannot
be resolved:

```python
import logging
from tvkit.symbols import normalize_symbol, SymbolNormalizationError

logger = logging.getLogger(__name__)

invalid_cases = [
    "AAPL",           # no exchange prefix (no default_exchange configured)
    "",               # empty string
    "INVALID SYMBOL", # internal whitespace
    "A:B:C",          # multiple colons
]

for sym in invalid_cases:
    try:
        normalize_symbol(sym)
    except SymbolNormalizationError as exc:
        logger.error("Invalid symbol %r: %s", exc.original, exc.reason)
```

`SymbolNormalizationError` is always raised before any network call. Errors from
`validate_symbols` (symbol not found in TradingView) remain `ValueError` and are a separate
concern.

---

## Migrating from `convert_symbol_format`

`tvkit.api.utils.convert_symbol_format` is deprecated as of v0.8.0. It emits a
`DeprecationWarning` on every call and will be removed in the next major version.

See [Migration Guide: Symbol Normalization](../development/migration-symbol-normalization.md)
for a complete before/after reference, field mapping, and error handling changes.

---

## See Also

- [`tvkit.symbols` reference](../reference/symbols/normalizer.md) — full API reference
- [Migration Guide](../development/migration-symbol-normalization.md) — `convert_symbol_format` → `normalize_symbol`
- [Symbols concept](../concepts/symbols.md) — symbol format and asset class examples
- [Historical Data guide](historical-data.md) — fetching bars for a symbol
