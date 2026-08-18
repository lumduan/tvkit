# Exporting Data

[Home](../index.md) > Guides > Exporting Data

`DataExporter` converts tvkit data — OHLCV bars or scanner results — into multiple output formats for analysis, storage, and data sharing. All export methods are async and return either a file path (for file exports) or a DataFrame (for in-memory exports).

## Prerequisites

- tvkit installed: see [Installation](../getting-started/installation.md)
- Fetch data first: see [Historical Data guide](historical-data.md) or [Scanner guide](scanner.md)

---

## Data Flow

```text
OHLCV bars / scanner results
        │
        │  DataExporter
        ▼
  ┌─────────────────────┐
  │   to_polars()       │──► polars.DataFrame  (in-memory)
  │   to_json()         │──► JSON file on disk
  │   to_csv()          │──► CSV file on disk
  └─────────────────────┘
  (Parquet via Polars: df.write_parquet())
```

---

## Supported Input Types

`DataExporter` accepts:

- `list[OHLCV]` — bars from `get_historical_ohlcv()` or a streaming buffer
- `list[ScannerStock]` — results from `ScannerService.scan_market()`

---

## Export Formats

| Method | Output | Use Case |
|--------|--------|----------|
| `to_polars()` | `polars.DataFrame` | In-memory analysis, further processing |
| `to_json()` | JSON file on disk | API responses, data sharing |
| `to_csv()` | CSV file on disk | Spreadsheets, backtesting tools |

Parquet export is available through Polars: `df.write_parquet("file.parquet")`. Prefer Parquet over CSV for large datasets — it is faster to read and write and preserves column types.

---

## Polars DataFrame Export

Convert OHLCV bars to a Polars DataFrame for in-memory analysis, with optional technical indicator columns:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def export_to_polars() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=90)

    exporter = DataExporter()
    df = await exporter.to_polars(bars, add_analysis=True)

    print(df.head(5))
    print(f"\nColumns: {df.columns}")

asyncio.run(export_to_polars())
```

**Output:**

```text
shape: (5, 6)
┌───────────────────────────┬────────┬─────────────┬─────────┬────────┬────────────┐
│ timestamp                 ┆ close  ┆ volume      ┆ sma_5   ┆ sma_10 ┆ vwap       │
│ ---                       ┆ ---    ┆ ---         ┆ ---     ┆ ---    ┆ ---        │
│ str                       ┆ f64    ┆ f64         ┆ f64     ┆ f64    ┆ f64        │
╞═══════════════════════════╪════════╪═════════════╪═════════╪════════╪════════════╡
│ 2026-04-09T13:30:00+00:00 ┆ 260.49 ┆ 2.8121574e7 ┆ null    ┆ null   ┆ 259.226667 │
│ 2026-04-10T13:30:00+00:00 ┆ 260.48 ┆ 3.1291473e7 ┆ null    ┆ null   ┆ 259.931206 │
│ 2026-04-13T13:30:00+00:00 ┆ 259.2  ┆ 3.6234698e7 ┆ null    ┆ null   ┆ 259.457206 │
│ 2026-04-14T13:30:00+00:00 ┆ 258.83 ┆ 4.837071e7  ┆ null    ┆ null   ┆ 259.410004 │
│ 2026-04-15T13:30:00+00:00 ┆ 266.43 ┆ 4.991351e7  ┆ 261.086 ┆ null   ┆ 260.48841  │
└───────────────────────────┴────────┴─────────────┴─────────┴────────┴────────────┘

Columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'return_pct', 'typical_price',
'true_range', 'vwap_numerator', 'sma_5', 'sma_10', 'vol_ma_5', 'cum_vwap_num', 'cum_volume',
'vwap', 'momentum_3']
```

# 90 rows total, showing 5 · showing 6 of 17 columns
# `timestamp` is a `String` — `to_polars()` uses timestamp_format="iso"

*Example output — live market values will differ.*

When `add_analysis=True`, these 11 columns are appended automatically:

- `return_pct` — percent change from the previous close
- `typical_price` — `(high + low + close) / 3`
- `true_range` — high−low based true range
- `vwap_numerator`, `cum_vwap_num`, `cum_volume`, `vwap` — Volume-Weighted Average Price and its running parts
- `sma_5`, `sma_10` — Simple Moving Averages
- `vol_ma_5` — 5-period volume moving average
- `momentum_3` — close minus close 3 bars ago

---

## JSON Export

Write OHLCV bars to a JSON file on disk, optionally including dataset metadata:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def export_to_json() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("BINANCE:BTCUSDT", "1D", bars_count=30)

    exporter = DataExporter()
    path = await exporter.to_json(
        bars,
        "./export/btc_daily.json",
        include_metadata=True,
    )
    print(f"Saved to: {path}")

asyncio.run(export_to_json())
```

**Output:**

```text
Saved to: export/btc_daily.json
```

The file itself (253 lines for 30 bars):

```json
{
  "data": [
    {
      "close": 65255.51,
      "high": 65799.0,
      "low": 63100.0,
      "open": 64722.55,
      "timestamp": "2026-07-20T00:00:00+00:00",
      "volume": 21323.48702
    },
    ...
  ],
  "metadata": {
    "export_timestamp": "2026-08-18 13:02:07.177502",
    "file_path": "export/btc_daily.json",
    "format": "json",
    "interval": null,
    "record_count": 30,
    "source": "ohlcv",
    "symbol": "unknown"
  }
}
```

# keys are alphabetical, not declaration order — the writer uses `sort_keys=True`

With `include_metadata=True`, the JSON file includes a `metadata` section containing symbol,
interval, bar count, and export timestamp. `symbol` is `"unknown"` and `interval` is `null` when
exporting a plain `list[OHLCVBar]` — neither is carried on the bar objects. Pass `interval=` to
`to_json()` to populate it.

---

## CSV Export

Write OHLCV bars to a CSV file for spreadsheet tools or external backtesting systems:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def export_to_csv() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=90)

    exporter = DataExporter()
    path = await exporter.to_csv(
        bars,
        "./export/aapl_daily.csv",
        include_metadata=True,
    )
    print(f"Saved to: {path}")

asyncio.run(export_to_csv())
```

**Output:**

```text
Saved to: export/aapl_daily.csv
```

`include_metadata=True` also writes a sidecar `export/aapl_daily.metadata.txt`. The CSV header is
`timestamp,open,high,low,close,volume`.

---

## Scanner Results Export

Export scanner results directly to Polars for analysis:

```python
import asyncio
from tvkit.api.scanner import ScannerService, Market
from tvkit.api.scanner import create_comprehensive_request
from tvkit.export import DataExporter

async def export_scanner_results() -> None:
    service = ScannerService()
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=50,
    )
    response = await service.scan_market(Market.AMERICA, request)

    exporter = DataExporter()
    df = await exporter.to_polars(response.data)

    # Save to Parquet for efficient storage
    df.write_parquet("./export/us_top50.parquet")
    print(f"Exported {df.shape[0]} stocks with {df.shape[1]} columns")

asyncio.run(export_scanner_results())
```

**Output:**

```text
Exported 50 stocks with 102 columns
```

# 101 requested columns + an `export_timestamp` String column the exporter always appends
# first: name, close, pricescale, minmov, fractional, minmove2, currency, change
# last:  open, change_abs, export_timestamp

---

## Custom Analysis with Polars

After exporting to a DataFrame, use Polars expressions for custom indicators:

```python
import asyncio
import polars as pl
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def custom_analysis() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", bars_count=200)

    exporter = DataExporter()
    df = await exporter.to_polars(bars, add_analysis=True)

    # Add Bollinger Bands and momentum.
    # add_analysis gives sma_5 and sma_10 — compute the 20-period mean inline.
    sma_20 = pl.col("close").rolling_mean(20)
    df = df.with_columns([
        (sma_20 + 2 * pl.col("close").rolling_std(20)).alias("bb_upper"),
        (sma_20 - 2 * pl.col("close").rolling_std(20)).alias("bb_lower"),
        (pl.col("volume") / pl.col("volume").rolling_mean(10)).alias("volume_ratio"),
        (pl.col("close") - pl.col("close").shift(5)).alias("momentum_5d"),
    ])

    df.write_parquet("./export/enhanced_analysis.parquet")
    print(f"Saved {df.shape[0]} rows with {df.shape[1]} columns")

asyncio.run(custom_analysis())
```

**Output:**

```text
Saved 200 rows with 21 columns
```

# 17 from add_analysis + bb_upper, bb_lower, volume_ratio, momentum_5d

---

## Export the Dataset Once, Then Export to Multiple Formats

Fetch the dataset once, then export it to multiple formats:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def export_all_formats(symbol: str) -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(symbol, "1D", bars_count=90)

    exporter = DataExporter()
    slug = symbol.replace(":", "_")

    df        = await exporter.to_polars(bars, add_analysis=True)
    json_path = await exporter.to_json(bars, f"./export/{slug}.json", include_metadata=True)
    csv_path  = await exporter.to_csv(bars, f"./export/{slug}.csv", include_metadata=True)

    print(f"DataFrame: {df.shape}")
    print(f"JSON:      {json_path}")
    print(f"CSV:       {csv_path}")

asyncio.run(export_all_formats("NASDAQ:AAPL"))
```

**Output:**

```text
DataFrame: (90, 17)
JSON:      export/NASDAQ_AAPL.json
CSV:       export/NASDAQ_AAPL.csv
```

# `to_json` / `to_csv` return a `Path`; `./export/` must already exist

---

## Performance Notes

For large datasets:

- Use Parquet instead of CSV for faster I/O and smaller file sizes
- Avoid exporting millions of rows to JSON — it is slow and not memory-efficient
- Prefer Polars DataFrames for in-memory analysis; write to Parquet for persistence
- For streaming data, flush buffers periodically rather than accumulating all bars in memory

---

## See Also

- [Historical Data guide](historical-data.md) — fetching OHLCV bars for export
- [Scanner guide](scanner.md) — fetching scanner results for export
- [DataExporter reference](../reference/export/exporter.md) — full method signatures and configuration
