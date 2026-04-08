# Migration Guide: Symbol Normalization

**Affects:** `tvkit.api.utils.convert_symbol_format`, `tvkit.api.utils.SymbolConversionResult`
**Replacement:** `tvkit.symbols.normalize_symbol`, `tvkit.symbols.NormalizedSymbol`
**Deprecated in:** v0.8.x (Phase 3 of the symbol normalization layer)
**Removed in:** future major version

---

## Why Migrate?

`convert_symbol_format` only handled one transformation: replacing a dash separator with a
colon (`NASDAQ-AAPL` → `NASDAQ:AAPL`). It did not normalize case, strip whitespace, or
raise errors for ambiguous bare tickers.

`tvkit.symbols.normalize_symbol` handles all symbol variants in one pass — before any
network I/O — ensuring `validate_symbols` always receives a well-formed `EXCHANGE:SYMBOL`
string. This eliminates an entire class of silent bugs where lowercased symbols or
whitespace-padded inputs would reach TradingView's HTTP endpoint in a non-canonical form.

---

## Quick Reference

| Old API | New API |
|---|---|
| `convert_symbol_format(sym)` | `normalize_symbol(sym)` |
| `convert_symbol_format([sym1, sym2])` | `normalize_symbols([sym1, sym2])` |
| `SymbolConversionResult` | `NormalizedSymbol` |
| `result.converted_symbol` | `result.canonical` |
| `result.original_symbol` | `result.original` |
| `result.is_converted` | `result.normalization_type != NormalizationType.ALREADY_CANONICAL` |

---

## Migration Examples

### Single symbol conversion

```python
# Before (deprecated)
from tvkit.api.utils import convert_symbol_format

result = convert_symbol_format("NASDAQ-AAPL")
canonical = result.converted_symbol   # "NASDAQ:AAPL"

# After
from tvkit.symbols import normalize_symbol

canonical = normalize_symbol("NASDAQ-AAPL")   # "NASDAQ:AAPL"
```

### Batch conversion

```python
# Before (deprecated)
from tvkit.api.utils import convert_symbol_format

results = convert_symbol_format(["NASDAQ-AAPL", "BINANCE:btcusdt"])
canonicals = [r.converted_symbol for r in results]
# ["NASDAQ:AAPL", "BINANCE:btcusdt"]  ← lowercase NOT fixed by old API

# After
from tvkit.symbols import normalize_symbols

canonicals = normalize_symbols(["NASDAQ-AAPL", "BINANCE:btcusdt"])
# ["NASDAQ:AAPL", "BINANCE:BTCUSDT"]  ← all formats handled
```

### Normalize then validate

```python
# Before (deprecated — validate ran on raw, possibly non-canonical input)
from tvkit.api.utils import convert_symbol_format, validate_symbols

await validate_symbols(exchange_symbol)            # raw input
result = convert_symbol_format(exchange_symbol)
canonical = result.converted_symbol

# After — normalize first (pure string, zero I/O), then validate
from tvkit.symbols import normalize_symbol
from tvkit.api.utils import validate_symbols

canonical = normalize_symbol(exchange_symbol)      # raises SymbolNormalizationError if invalid
await validate_symbols(canonical)                  # always receives canonical form
```

### Rich result model

```python
# Before (deprecated)
from tvkit.api.utils import convert_symbol_format, SymbolConversionResult

result: SymbolConversionResult = convert_symbol_format("NASDAQ-AAPL")
print(result.original_symbol)    # "NASDAQ-AAPL"
print(result.converted_symbol)   # "NASDAQ:AAPL"
print(result.is_converted)       # True

# After
from tvkit.symbols import normalize_symbol_detailed, NormalizedSymbol, NormalizationType

result: NormalizedSymbol = normalize_symbol_detailed("NASDAQ-AAPL")
print(result.original)           # "NASDAQ-AAPL"
print(result.canonical)          # "NASDAQ:AAPL"
print(result.exchange)           # "NASDAQ"
print(result.ticker)             # "AAPL"
print(result.normalization_type) # NormalizationType.DASH_TO_COLON
```

---

## Error Handling Changes

`convert_symbol_format` never raised for invalid symbols — it returned the input unchanged.
`normalize_symbol` raises `SymbolNormalizationError` immediately for inputs that cannot be
normalized to a valid `EXCHANGE:SYMBOL` form.

```python
# Before — silent pass-through (symbol reaches TradingView as-is)
result = convert_symbol_format("AAPL")
print(result.converted_symbol)   # "AAPL" — no error, no exchange prefix

# After — fail-fast (error before any I/O)
from tvkit.symbols import normalize_symbol, SymbolNormalizationError

try:
    canonical = normalize_symbol("AAPL")
except SymbolNormalizationError as exc:
    print(exc)  # Cannot normalize 'AAPL': no exchange prefix
```

### Callers catching `ValueError` for format errors

Previously, some callers caught `ValueError` raised by `validate_symbols` as a proxy for
"bad symbol format". With the new pattern, format errors are `SymbolNormalizationError`
(raised before I/O) and network validation errors remain `ValueError` (raised by
`validate_symbols` when the symbol doesn't exist in TradingView).

```python
# Before
try:
    await validate_symbols(sym)
    result = convert_symbol_format(sym)
except ValueError as exc:
    handle_bad_symbol(exc)

# After — separate the two error types
from tvkit.symbols import normalize_symbol, SymbolNormalizationError

try:
    canonical = normalize_symbol(sym)     # format errors
except SymbolNormalizationError as exc:
    handle_format_error(exc)
    raise

try:
    await validate_symbols(canonical)     # network / existence errors
except ValueError as exc:
    handle_not_found(exc)
    raise
```

---

## Bare Ticker Support (Phase 2)

`convert_symbol_format` had no support for bare tickers. `normalize_symbol` can resolve
bare tickers when a `default_exchange` is configured:

```python
from tvkit.symbols import normalize_symbol, NormalizationConfig

config = NormalizationConfig(default_exchange="NASDAQ")
canonical = normalize_symbol("AAPL", config=config)   # "NASDAQ:AAPL"
```

Or via the `TVKIT_DEFAULT_EXCHANGE` environment variable:

```bash
export TVKIT_DEFAULT_EXCHANGE=NASDAQ
```

```python
canonical = normalize_symbol("AAPL")   # "NASDAQ:AAPL"
```

---

## Deprecation Timeline

| Version | Status |
|---|---|
| v0.8.x | `convert_symbol_format` and `SymbolConversionResult` deprecated with `DeprecationWarning` |
| Next major | Both removed |

Until removed, both APIs remain importable. `convert_symbol_format` will emit a
`DeprecationWarning` on every call. Use `warnings.filterwarnings("ignore", category=DeprecationWarning)`
temporarily during migration if you need to suppress warnings in CI.
