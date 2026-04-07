# `tvkit.symbols` — Symbol Normalization

**Module:** `tvkit.symbols`
**Phase:** 1 (exchange-aware inputs only)
**Source:** `tvkit/symbols/`

---

## Overview

`tvkit.symbols` provides a synchronous, pure-string normalization layer that converts any
exchange-aware TradingView instrument reference to the canonical `EXCHANGE:SYMBOL` form
(uppercase, colon-separated).

It is a **leaf module** — it imports nothing from `tvkit.api` or `tvkit.export`, so it can
be used anywhere in the codebase without circular-import risk.

All functions are **synchronous** (no `async`/`await`). Symbol normalization involves no I/O.

---

## Quick start

```python
from tvkit.symbols import normalize_symbol, normalize_symbols, SymbolNormalizationError

# All of these return "NASDAQ:AAPL"
normalize_symbol("NASDAQ:AAPL")
normalize_symbol("nasdaq:aapl")
normalize_symbol("NASDAQ-AAPL")
normalize_symbol("  NASDAQ:AAPL  ")

# Batch — 1:1, preserves order, raises on first invalid
normalize_symbols(["NASDAQ:AAPL", "BINANCE:btcusdt"])
# → ["NASDAQ:AAPL", "BINANCE:BTCUSDT"]

# Error on bare ticker (no exchange prefix)
try:
    normalize_symbol("AAPL")
except SymbolNormalizationError as exc:
    print(exc)           # Cannot normalize 'AAPL': no exchange prefix
    print(exc.original)  # AAPL
    print(exc.reason)    # no exchange prefix
```

---

## Normalization rules

Rules are applied in the following order:

| Step | Rule |
|------|------|
| 1 | Strip leading/trailing whitespace (`config.strip_whitespace=True` by default) |
| 2 | Raise `SymbolNormalizationError` if empty after strip |
| 3 | Uppercase entire string |
| 4 | If no `:` **and** exactly one `-`: replace `-` with `:` |
| 5 | Validate against `^[A-Z0-9_]+:[A-Z0-9._!]+$` |
| 6 | Return canonical string |

### Supported character sets

| Component | Allowed characters | Examples |
|-----------|-------------------|---------|
| Exchange  | `[A-Z0-9_]` | `NASDAQ`, `FX_IDC`, `CME_MINI` |
| Ticker    | `[A-Z0-9._!]` | `AAPL`, `BRK.B`, `ES1!`, `BTCUSDT` |

### Input → output examples

| Input | Output | Rule applied |
|-------|--------|-------------|
| `"NASDAQ:AAPL"` | `"NASDAQ:AAPL"` | none (already canonical) |
| `"nasdaq:aapl"` | `"NASDAQ:AAPL"` | uppercase |
| `"NASDAQ-AAPL"` | `"NASDAQ:AAPL"` | dash → colon |
| `"nasdaq-aapl"` | `"NASDAQ:AAPL"` | uppercase + dash → colon |
| `"  NASDAQ:AAPL  "` | `"NASDAQ:AAPL"` | strip whitespace |
| `"FX_IDC:eurusd"` | `"FX_IDC:EURUSD"` | uppercase |
| `"NYSE:BRK.B"` | `"NYSE:BRK.B"` | none |
| `"CME_MINI:ES1!"` | `"CME_MINI:ES1!"` | none |
| `"BINANCE:btcusdt"` | `"BINANCE:BTCUSDT"` | uppercase |

### Invalid inputs (examples)

| Input | Reason |
|-------|--------|
| `"AAPL"` | no exchange prefix |
| `""` | symbol must not be empty |
| `"   "` | symbol must not be empty after stripping whitespace |
| `"INVALID SYMBOL"` | symbol must not contain internal whitespace |
| `"NYSE:AAPL:USD"` | symbol contains multiple ':' separators |
| `"NASDAQ--AAPL"` | two dashes → no colon after step 4, `"no exchange prefix"` |
| `":AAPL"` | exchange component must not be empty after normalization |
| `"NASDAQ:"` | ticker component must not be empty after normalization |
| `"NASDAQ:AAPL@"` | symbol components must contain only valid characters |

> **Note on multiple dashes:** `"NASDAQ--AAPL"` has two dashes. Step 4 only fires when
> there is *exactly one* dash and no colon, so no conversion is attempted and the string
> fails validation with `"no exchange prefix"`.

---

## Functions

### `normalize_symbol`

```python
def normalize_symbol(
    symbol: str,
    *,
    config: NormalizationConfig | None = None,
) -> str
```

Normalize a single symbol. Returns the canonical string directly.

**Args:**
- `symbol` — symbol string in any supported variant. Must be a `str`.
- `config` — optional `NormalizationConfig`. Defaults to `NormalizationConfig()`.

**Returns:** `str` — canonical `EXCHANGE:SYMBOL`.

**Raises:** `SymbolNormalizationError` if the symbol cannot be normalized or is not a `str`.

---

### `normalize_symbols`

```python
def normalize_symbols(
    symbols: list[str],
    *,
    config: NormalizationConfig | None = None,
) -> list[str]
```

Normalize a list of symbols. **1:1 mapping** — input order is preserved, duplicates are not
removed. Raises on the first invalid element.

**Args:**
- `symbols` — must be a `list`. Passing a plain `str` raises `SymbolNormalizationError`
  to avoid silent character-by-character iteration.
- `config` — optional `NormalizationConfig`.

**Returns:** `list[str]` — same length and order as input.

**Raises:** `SymbolNormalizationError` if `symbols` is not a `list`, or on the first invalid
element.

---

### `normalize_symbol_detailed`

```python
def normalize_symbol_detailed(
    symbol: str,
    *,
    config: NormalizationConfig | None = None,
) -> NormalizedSymbol
```

Normalize a single symbol and return a rich result model with metadata.

Use this when you need to inspect *how* a symbol was normalized (e.g. audit logging,
pipeline tracing). For most call sites, `normalize_symbol` returning a plain `str` is
preferred.

**Args:**
- `symbol` — symbol string in any supported variant. Must be a `str`.
- `config` — optional `NormalizationConfig`.

**Returns:** `NormalizedSymbol`.

**Raises:** `SymbolNormalizationError` if the symbol cannot be normalized or is not a `str`.

**Example:**

```python
from tvkit.symbols import normalize_symbol_detailed, NormalizationType

result = normalize_symbol_detailed("NASDAQ-AAPL")
print(result.canonical)          # "NASDAQ:AAPL"
print(result.exchange)           # "NASDAQ"
print(result.ticker)             # "AAPL"
print(result.original)           # "NASDAQ-AAPL"
print(result.normalization_type) # NormalizationType.DASH_TO_COLON

result2 = normalize_symbol_detailed("  nasdaq:aapl  ")
print(result2.normalization_type) # NormalizationType.WHITESPACE_STRIP
# Whitespace strip takes precedence even though uppercase was also applied.
```

---

## Data models

### `NormalizedSymbol`

```python
class NormalizedSymbol(BaseModel):
    canonical: str           # "NASDAQ:AAPL"
    exchange: str            # "NASDAQ"
    ticker: str              # "AAPL"
    original: str            # original input string (unchanged)
    normalization_type: NormalizationType
```

Frozen Pydantic model. All fields are validated at construction time:
- `canonical` matches `^[A-Z0-9_]+:[A-Z0-9._!]+$`
- `exchange` matches `^[A-Z0-9_]+$` and is non-empty
- `ticker` matches `^[A-Z0-9._!]+$` and is non-empty
- `original` is non-empty and not whitespace-only
- `canonical == f"{exchange}:{ticker}"`

---

### `NormalizationType`

```python
class NormalizationType(str, Enum):
    ALREADY_CANONICAL = "already_canonical"
    DASH_TO_COLON     = "dash_to_colon"
    UPPERCASE_ONLY    = "uppercase_only"
    WHITESPACE_STRIP  = "whitespace_strip"
    DEFAULT_EXCHANGE  = "default_exchange"   # Phase 2 placeholder
```

Records the **primary** transformation applied. When multiple transforms are applied,
the highest-priority one is recorded:

| Priority | Type | When assigned |
|----------|------|---------------|
| 1 | `WHITESPACE_STRIP` | Input had leading or trailing whitespace |
| 2 | `DASH_TO_COLON` | Dash replaced with colon |
| 3 | `UPPERCASE_ONLY` | Only case-folding applied |
| 4 | `ALREADY_CANONICAL` | No change needed |

`DEFAULT_EXCHANGE` is reserved for Phase 2 bare-ticker resolution.

---

### `NormalizationConfig`

```python
class NormalizationConfig(BaseModel):
    default_exchange: str | None = None
    strip_whitespace: bool = True
```

Frozen model that controls normalization behaviour. This is a **function-behaviour model**,
not environment-backed runtime settings — it does not read from environment variables
and is not equivalent to application configuration.

> **Phase 1 temporary deviation:** CLAUDE.md requires all configuration to use Pydantic
> Settings. `NormalizationConfig` uses plain `BaseModel` because `pydantic-settings` is not
> yet declared in `pyproject.toml`. Phase 2 upgrades it to `BaseSettings` with
> `env_prefix="TVKIT_"` — same field names, no breaking change.

**`strip_whitespace=False`** — whitespace is not stripped; symbols with leading/trailing
whitespace raise `SymbolNormalizationError` with a message explaining how to fix the input.

**`default_exchange`** — accepted in Phase 1 but bare-ticker resolution is not active until
Phase 2. Must be a valid uppercase exchange identifier when provided (e.g. `"NASDAQ"`,
`"FX_IDC"`). An empty string or whitespace-only value raises a `ValidationError`.

```python
# Phase 1: default_exchange is accepted but has no effect on bare tickers
config = NormalizationConfig(default_exchange="NASDAQ")
normalize_symbol("AAPL", config=config)
# → SymbolNormalizationError: Cannot normalize 'AAPL': no exchange prefix
```

---

## Error handling

### `SymbolNormalizationError`

```python
class SymbolNormalizationError(ValueError):
    original: str   # the input value that failed (as str or repr for non-str)
    reason: str     # human-readable explanation
```

Subclass of `ValueError`. Always raised with both `original` and `reason`.

| Condition | `reason` message |
|-----------|-----------------|
| Empty string | `"symbol must not be empty"` |
| Whitespace-only | `"symbol must not be empty after stripping whitespace"` |
| No exchange prefix | `"no exchange prefix"` |
| Multiple `:` | `"symbol contains multiple ':' separators"` |
| Internal whitespace | `"symbol must not contain internal whitespace"` |
| Leading/trailing whitespace with `strip_whitespace=False` | `"symbol has leading or trailing whitespace; set strip_whitespace=True or strip the input before normalizing"` |
| Empty exchange component (`":AAPL"`) | `"exchange component must not be empty after normalization"` |
| Empty ticker component (`"NASDAQ:"`) | `"ticker component must not be empty after normalization"` |
| Invalid characters | `"symbol components must contain only valid characters"` |
| Non-`str` `symbol` | `"symbol must be a str, got <typename>"` |
| Non-`list` `symbols` | `"symbols must be a list of str, got <typename>"` |

---

## Phase scope

| Feature | Status |
|---------|--------|
| Exchange-aware symbol normalization | **Phase 1 — available** |
| Bare-ticker resolution via `default_exchange` | Phase 2 |
| `TVKIT_DEFAULT_EXCHANGE` env var support | Phase 2 |
| Crypto slash-pair normalization (`BTC/USDT`) | Phase 2 |
| Integration into `ohlcv.py` call sites | Phase 3 |
| Deprecation of `convert_symbol_format` | Phase 3 |
