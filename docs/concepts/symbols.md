# Symbols

[Home](../index.md) > Concepts > Symbols

A **symbol** in tvkit identifies a financial instrument. Every symbol is a string composed of an exchange prefix and a ticker, separated by a colon.

## Format

```
EXCHANGE:TICKER
```

| Part | Description | Example |
|------|-------------|---------|
| `EXCHANGE` | TradingView exchange or data provider identifier | `NASDAQ`, `BINANCE`, `INDEX` |
| `TICKER` | Instrument identifier on that exchange | `AAPL`, `BTCUSDT`, `NDFI` |

The colon separator is required. TradingView's WebSocket API rejects symbols that use any other delimiter.

## Asset Class Examples

| Asset Class | Symbol | Notes |
|-------------|--------|-------|
| US Equity | `NASDAQ:AAPL` | Exchange must match the primary listing |
| US Equity | `NYSE:IBM` | — |
| Crypto | `BINANCE:BTCUSDT` | Perpetual futures use exchange-specific notation |
| Crypto | `COINBASE:ETHUSD` | — |
| Forex | `FX_IDC:EURUSD` | `FOREX:` is not a TradingView exchange prefix |
| Forex | `OANDA:XAUUSD` | Gold quoted in USD |
| Index | `INDEX:SPX` | TradingView index identifiers |
| Macro Indicator | `INDEX:NDFI` | Net Demand For Income |
| Macro Indicator | `USI:PCC` | Put/Call Ratio |
| Thai Equity | `SET:PTT` | Country-specific exchanges supported |

## Symbol Normalization

tvkit automatically normalizes symbols to the canonical `EXCHANGE:SYMBOL` form (uppercase,
colon-separated) before any API call. Normalization is synchronous, involves no network I/O,
and runs before validation.

```python
from tvkit.symbols import normalize_symbol

# All of these produce "NASDAQ:AAPL"
normalize_symbol("nasdaq:aapl")       # lowercase
normalize_symbol("NASDAQ-AAPL")       # dash separator
normalize_symbol("  NASDAQ:AAPL  ")   # whitespace padding
normalize_symbol("NASDAQ:AAPL")       # already canonical — returned unchanged
```

**Output:**

| Input | Return value |
|---|---|
| `"nasdaq:aapl"` | `'NASDAQ:AAPL'` |
| `"NASDAQ-AAPL"` | `'NASDAQ:AAPL'` |
| `"  NASDAQ:AAPL  "` | `'NASDAQ:AAPL'` |
| `"NASDAQ:AAPL"` | `'NASDAQ:AAPL'` |

`normalize_symbol` returns a plain `str` and performs no I/O.

Supported input variants:

| Input | Canonical output |
|-------|-----------------|
| `NASDAQ:AAPL` | `NASDAQ:AAPL` |
| `nasdaq:aapl` | `NASDAQ:AAPL` |
| `NASDAQ-AAPL` | `NASDAQ:AAPL` |
| `  NASDAQ:AAPL  ` | `NASDAQ:AAPL` |
| `BINANCE:btcusdt` | `BINANCE:BTCUSDT` |
| `FX_IDC:eurusd` | `FX_IDC:EURUSD` |
| `CME_MINI:ES1!` | `CME_MINI:ES1!` |

### Bare-ticker resolution

Symbols without an exchange prefix (e.g. `AAPL`) require a `default_exchange` to be configured:

```python
from tvkit.symbols import normalize_symbol, NormalizationConfig

config = NormalizationConfig(default_exchange="NASDAQ")
normalize_symbol("AAPL", config=config)   # → "NASDAQ:AAPL"
```

Or via the `TVKIT_DEFAULT_EXCHANGE` environment variable:

```bash
export TVKIT_DEFAULT_EXCHANGE=NASDAQ
```

See [Symbol Normalization guide](../guides/symbol-normalization.md) and the
[`tvkit.symbols` reference](../reference/symbols/normalizer.md) for the full API.

## Validation

tvkit validates symbol existence before sending WebSocket requests. The call ordering is:

1. `normalize_symbol(raw)` — pure-string transformation, raises `SymbolNormalizationError` for
   malformed inputs (no network call)
2. `validate_symbols(canonical)` — HTTP check against TradingView, raises `ValueError` if the
   symbol does not exist

Use `validate_symbols()` from `tvkit.api.utils` to check symbol existence before use:

```python
from tvkit.symbols import normalize_symbol
from tvkit.api.utils import validate_symbols

canonical = normalize_symbol("nasdaq:aapl")          # → "NASDAQ:AAPL"
await validate_symbols(canonical)                    # raises ValueError if not found
```

**Output:**

```text
True
```

`validate_symbols` returns `True` for a symbol TradingView knows, and raises `ValueError`
otherwise — it never returns `False`.

See [tvkit.api.utils reference](../reference/chart/utils.md) for full parameter documentation.

## See Also

- [Symbol Normalization guide](../guides/symbol-normalization.md) — step-by-step normalization workflows
- [`tvkit.symbols` reference](../reference/symbols/normalizer.md) — full API reference
- [Intervals](intervals.md) — timeframe strings used alongside symbols
- [Historical Data guide](../guides/historical-data.md) — fetching bars for a symbol
- [Real-time Streaming guide](../guides/realtime-streaming.md) — streaming a symbol live
