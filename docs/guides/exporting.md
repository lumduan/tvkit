# Exporting Data

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

When `add_analysis=True`, the following columns are appended automatically:

- `sma_20`, `sma_50` — Simple Moving Averages
- `vwap` — Volume-Weighted Average Price
- `rsi` — Relative Strength Index (14-period)

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

With `include_metadata=True`, the JSON file includes a `metadata` section containing symbol, interval, bar count, and export timestamp.

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
    response = await service.scan_market(Market.US, request)

    exporter = DataExporter()
    df = await exporter.to_polars(response.data)

    # Save to Parquet for efficient storage
    df.write_parquet("./export/us_top50.parquet")
    print(f"Exported {df.shape[0]} stocks with {df.shape[1]} columns")

asyncio.run(export_scanner_results())
```

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

    # Add Bollinger Bands and momentum
    df = df.with_columns([
        (pl.col("sma_20") + 2 * pl.col("close").rolling_std(20)).alias("bb_upper"),
        (pl.col("sma_20") - 2 * pl.col("close").rolling_std(20)).alias("bb_lower"),
        (pl.col("volume") / pl.col("volume").rolling_mean(10)).alias("volume_ratio"),
        (pl.col("close") - pl.col("close").shift(5)).alias("momentum_5d"),
    ])

    df.write_parquet("./export/enhanced_analysis.parquet")
    print(f"Saved {df.shape[0]} rows with {df.shape[1]} columns")

asyncio.run(custom_analysis())
```

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
