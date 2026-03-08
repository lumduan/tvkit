# Macro Indicators

[Home](../index.md) > Guides > Macro Indicators

tvkit can access TradingView macro and sentiment indicators — `INDEX:NDFI` and `USI:PCC` — using the same `get_historical_ohlcv()` and `get_ohlcv()` methods used for equities or crypto symbols. No special configuration is required.

## Prerequisites

- tvkit installed: see [Installation](../getting-started/installation.md)
- Understand symbol format: see [Symbols](../concepts/symbols.md)
- Understand intervals: see [Intervals](../concepts/intervals.md)

---

## Typical Use Cases

- Risk filters for systematic trading strategies
- Portfolio allocation signals based on liquidity conditions
- Market regime detection (risk-on vs risk-off)
- Sentiment extremes for contrarian entry and exit signals

---

## When to Use Macro Indicators

These indicators complement price-based signals when you need insight into:

- The overall demand for defensive income assets
- The level of fear or complacency in the options market
- Whether current conditions favour equities or defensive assets

---

## Supported Indicators

| Symbol | Name | Interpretation |
|--------|------|---------------|
| `INDEX:NDFI` | Net Demand For Income | High values = strong demand for income assets (defensive positioning) |
| `USI:PCC` | Put/Call Ratio | High values = fear (contrarian bullish); low values = complacency (contrarian bearish) |

Both indicators are available on daily (`"1D"`) intervals. Intraday intervals typically return no data.

---

## Fetching Historical Data

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.utils import convert_timestamp_to_iso

async def fetch_macro_indicators() -> None:
    async with OHLCV() as client:
        ndfi = await client.get_historical_ohlcv("INDEX:NDFI", "1D", bars_count=100)
        pcc  = await client.get_historical_ohlcv("USI:PCC",   "1D", bars_count=100)

    print(f"NDFI: {len(ndfi)} bars  latest={ndfi[-1].close:.6f}")
    print(f"PCC:  {len(pcc)} bars  latest={pcc[-1].close:.4f}")

    for bar in ndfi[-5:]:
        date = convert_timestamp_to_iso(bar.timestamp)[:10]
        print(f"  {date}  NDFI={bar.close:.6f}")

asyncio.run(fetch_macro_indicators())
```

---

## Percentile Rank — Core Calculation

All regime detection in this guide uses a **percentile rank**: what fraction of historical values is at or below the current reading. For example, a value at the 90th percentile is higher than 90% of observations in the lookback window.

Define the helper once and reuse it across all examples:

```python
def percentile_rank(values: list[float], current: float) -> float:
    """Return the percentile (0–100) of `current` within `values`."""
    return sum(1 for v in values if v <= current) / len(values) * 100
```

A 252-bar window (~1 trading year) is recommended for daily indicators.

---

## Liquidity Regime Detection (INDEX:NDFI)

NDFI measures net demand for income-generating assets. Elevated readings signal that investors are rotating into defensive, yield-bearing positions.

| NDFI Percentile | Regime | Interpretation |
|-----------------|--------|---------------|
| > 75th | Defensive | Strong demand for income assets |
| 25–75th | Neutral | No strong macro signal |
| < 25th | Risk-on | Investors favour risk assets |

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

def percentile_rank(values: list[float], current: float) -> float:
    return sum(1 for v in values if v <= current) / len(values) * 100

async def detect_liquidity_regime() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("INDEX:NDFI", "1D", bars_count=252)

    values  = [b.close for b in bars]
    current = bars[-1].close
    pct     = percentile_rank(values, current)

    if pct > 75:
        regime = "DEFENSIVE — strong demand for income assets"
    elif pct < 25:
        regime = "RISK-ON   — investors favour risk assets"
    else:
        regime = "NEUTRAL"

    print(f"NDFI = {current:.6f}  ({pct:.1f}th percentile)")
    print(f"Regime: {regime}")

asyncio.run(detect_liquidity_regime())
```

---

## Sentiment Analysis (USI:PCC)

The Put/Call Ratio measures options market sentiment. High values indicate heavy demand for downside protection, which historically occurs near market bottoms. Low values signal complacency, which historically occurs near market tops.

| PCC Percentile | Sentiment | Signal |
|----------------|-----------|--------|
| > 80th | Extreme fear | Contrarian bullish |
| 20–80th | Neutral | No strong signal |
| < 20th | Complacency | Contrarian bearish |

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

def percentile_rank(values: list[float], current: float) -> float:
    return sum(1 for v in values if v <= current) / len(values) * 100

async def analyze_sentiment() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("USI:PCC", "1D", bars_count=252)

    values  = [b.close for b in bars]
    current = bars[-1].close
    pct     = percentile_rank(values, current)

    if pct > 80:
        signal = "EXTREME FEAR    → contrarian bullish"
    elif pct < 20:
        signal = "COMPLACENCY     → contrarian bearish"
    else:
        signal = "NEUTRAL"

    print(f"PCC = {current:.4f}  ({pct:.1f}th percentile)")
    print(f"Sentiment: {signal}")

asyncio.run(analyze_sentiment())
```

---

## Combined Regime Score

Average NDFI and PCC percentiles into a single risk-posture score. When both NDFI and PCC are elevated simultaneously, the market shows strong demand for defensive income assets and heavy demand for downside protection — a classic risk-off environment.

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

def percentile_rank(values: list[float], current: float) -> float:
    return sum(1 for v in values if v <= current) / len(values) * 100

async def combined_regime_score() -> None:
    async with OHLCV() as client:
        ndfi_bars = await client.get_historical_ohlcv("INDEX:NDFI", "1D", bars_count=252)
        pcc_bars  = await client.get_historical_ohlcv("USI:PCC",   "1D", bars_count=252)

    ndfi_pct   = percentile_rank([b.close for b in ndfi_bars], ndfi_bars[-1].close)
    pcc_pct    = percentile_rank([b.close for b in pcc_bars],  pcc_bars[-1].close)
    risk_score = (ndfi_pct + pcc_pct) / 2

    print(f"NDFI percentile: {ndfi_pct:.1f}")
    print(f"PCC percentile:  {pcc_pct:.1f}")
    print(f"Risk score:      {risk_score:.1f}", end="  →  ")

    if risk_score > 70:
        print("Risk-OFF: consider reducing equity exposure")
    elif risk_score < 30:
        print("Risk-ON: conditions favour equities")
    else:
        print("Neutral: maintain current allocation")

asyncio.run(combined_regime_score())
```

---

## Real-time Monitoring

Macro indicators update once per trading day. Streaming is useful for detecting the daily close update as soon as it is published on TradingView.

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def stream_macro_indicators() -> None:
    async with OHLCV() as client:
        async for bar in client.get_ohlcv("INDEX:NDFI", interval="1D"):
            print(f"NDFI daily close update: {bar.close:.6f}")

asyncio.run(stream_macro_indicators())
```

---

## See Also

- [Symbols](../concepts/symbols.md) — `INDEX:` and `USI:` exchange prefix format
- [Intervals](../concepts/intervals.md) — daily intervals for macro indicators
- [Streaming vs Historical](../concepts/streaming-vs-historical.md) — choosing access pattern
- [Historical Data guide](historical-data.md) — date-range mode for longer lookback windows
- [Real-time Streaming guide](realtime-streaming.md) — streaming live updates
