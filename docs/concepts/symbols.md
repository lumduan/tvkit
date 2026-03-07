# Symbols

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
| Forex | `FOREX:EURUSD` | Uses `FOREX` as the exchange prefix |
| Forex | `OANDA:XAUUSD` | Gold quoted in USD |
| Index | `INDEX:SPX` | TradingView index identifiers |
| Macro Indicator | `INDEX:NDFI` | Net Demand For Income |
| Macro Indicator | `USI:PCC` | Put/Call Ratio |
| Thai Equity | `SET:PTT` | Country-specific exchanges supported |

## Dash-to-Colon Automatic Conversion

tvkit automatically converts dash-format symbols to colon format before sending them to TradingView. This means `USI-PCC` and `USI:PCC` are treated identically by all tvkit methods.

The conversion is one-way: if the symbol already contains a colon, it is not modified.

```python
# Both of these are equivalent:
await client.get_historical_ohlcv("USI:PCC", "1D", 100)
await client.get_historical_ohlcv("USI-PCC", "1D", 100)
```

Prefer the colon format in your code. The dash format is provided for compatibility with data sources that use a different convention.

## Validation

tvkit does not validate symbol existence before sending a request. If a symbol is invalid, TradingView returns no data. Use `validate_symbols()` from `tvkit.api.utils` to check symbol validity before use:

```python
from tvkit.api.utils import validate_symbols

result = await validate_symbols(["NASDAQ:AAPL", "BOGUS:XYZ"])
```

See [tvkit.api.utils reference](../reference/chart/utils.md) for full parameter documentation.

## See Also

- [Intervals](intervals.md) — timeframe strings used alongside symbols
- [Historical Data guide](../guides/historical-data.md) — fetching bars for a symbol
- [Real-time Streaming guide](../guides/realtime-streaming.md) — streaming a symbol live
