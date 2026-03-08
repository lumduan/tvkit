# Data Sources

tvkit fetches all data from TradingView's WebSocket and HTTP APIs. This page describes what TradingView provides, where its data originates, and the coverage gaps you should know about.

## Data Origin

TradingView does not operate its own exchange feeds. It aggregates price data from:

- **Exchange direct feeds** — for major exchanges where TradingView has data agreements (e.g., NASDAQ, NYSE, Binance)
- **Data vendor redistribution** — for smaller or international markets where exchange-direct feeds are impractical
- **Calculated series** — for indices, macro indicators (NDFI, PCC), and composite instruments

This aggregation means data quality varies by exchange. Major US equities and crypto pairs are typically high quality; smaller international exchanges may have gaps or infrequent updates.

## Real-time vs Delayed Data

Whether you receive real-time or delayed data depends on your TradingView account tier, not on tvkit configuration.

| Market | Free | Pro / Premium |
|--------|------|--------------|
| US equities (NASDAQ, NYSE) | 15-min delay | Real-time |
| European equities | Exchange-dependent delay | Real-time or reduced delay |
| Asian equities | Exchange-dependent delay | Real-time or reduced delay |
| Crypto (Binance, Coinbase, etc.) | Real-time | Real-time |
| Forex (major pairs) | Real-time | Real-time |
| Macro indicators (NDFI, PCC) | End-of-day | End-of-day |

tvkit has no mechanism to determine whether data is delayed — the `OHLCV` bar's `timestamp` reflects the bar's actual close time, not a delivery timestamp.

## Market Coverage by Region

tvkit's scanner API supports 69 markets across five regions:

| Region | Markets | Notable Exchanges |
|--------|---------|-----------------|
| North America | 2 | NASDAQ, NYSE (USA); TSX, TSXV (Canada) |
| Europe | 30 | XETRA (Germany); LSE (UK); Euronext (France, Netherlands); SIX (Switzerland) |
| Asia Pacific | 17 | TSE (Japan); SET (Thailand); SGX (Singapore); ASX (Australia); NSE (India) |
| Middle East & Africa | 12 | ADX, DFM (UAE); Tadawul (Saudi Arabia); TASE (Israel); JSE (South Africa) |
| Latin America | 7 | B3 (Brazil); BMV (Mexico); BCS (Chile); BVC (Colombia) |

Chart API (OHLCV streaming and historical) supports any symbol available on TradingView, regardless of region.

## Supported Asset Classes

| Asset Class | Scanner API | Chart API |
|-------------|------------|----------|
| Equities | Yes | Yes |
| ETFs | Yes | Yes |
| Crypto | Limited | Yes |
| Forex | No | Yes |
| Indices | No | Yes |
| Macro indicators | No | Yes (daily) |
| Futures | No | No |
| Options | No | No |

## Data Quality Notes

- **OHLCV bars**: Sourced from exchange feeds or vendor aggregation. Minor discrepancies from exchange-native feeds are possible.
- **Scanner fundamentals**: Sourced from financial data vendors. Some fields (e.g., EPS estimates, analyst ratings) may be stale for smaller companies with less analyst coverage.
- **Macro indicators**: Calculated by TradingView. Methodology is not publicly documented; use as a relative signal, not an absolute figure.
- **Crypto**: Real-time, but prices reflect TradingView's composite or the specified exchange feed (e.g., `BINANCE:BTCUSDT` uses Binance's feed specifically).

## What tvkit Does Not Modify

tvkit parses TradingView responses into typed Python objects and applies no adjustments, normalization, or quality filtering. The data you receive is the data TradingView sends. If TradingView has a gap or an anomalous value, tvkit will pass it through.

## See Also

- [Limitations](limitations.md) — bar caps, rate limits, and unsupported data types
- [Why tvkit?](why-tvkit.md) — design goals and scope
- [Symbols](concepts/symbols.md) — symbol format and exchange prefix conventions
