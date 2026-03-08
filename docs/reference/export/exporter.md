# DataExporter Reference

**Module:** `tvkit.export`
**Introduced in:** v0.1.0

Unified interface for exporting tvkit financial data to Polars DataFrames, JSON files, and CSV files. Handles `OHLCVBar` data from the chart API and `StockData` from the scanner API through the same methods.

## Quick Example

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def main() -> None:
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", interval="1D", bars_count=100)

    exporter = DataExporter()
    df = await exporter.to_polars(bars)          # Polars DataFrame
    await exporter.to_csv(bars, "aapl.csv")      # CSV file + metadata sidecar
    await exporter.to_json(bars, "aapl.json")    # JSON file with metadata

asyncio.run(main())
```

---

## Import

```python
from tvkit.export import (
    DataExporter,
    ExportFormat,
    ExportConfig,
    ExportResult,
    ExportMetadata,
)
```

---

## `DataExporter`

Primary export class. No configuration is required at construction time — all options are passed per-call via `ExportConfig` or method parameters.

### Signature

```python
class DataExporter:
    def __init__(self) -> None: ...
```

Registers three built-in formatters on initialization: `POLARS`, `JSON`, `CSV`. `PARQUET` is defined in `ExportFormat` but is **not registered** — calling any export method with `ExportFormat.PARQUET` raises `ValueError`. Use `add_formatter()` to register a custom Parquet formatter if needed.

---

## Methods

### `export_ohlcv_data()`

Low-level export method for OHLCV data with full format and configuration control.

```python
async def export_ohlcv_data(
    self,
    data: list[OHLCVBar],
    format: ExportFormat,
    file_path: Path | str | None = None,
    config: ExportConfig | None = None,
) -> ExportResult: ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | `list[OHLCVBar]` | required | OHLCV bars from `get_historical_ohlcv()` or `get_ohlcv()` |
| `format` | `ExportFormat` | required | Target format (`POLARS`, `JSON`, or `CSV`) |
| `file_path` | `Path \| str \| None` | `None` | Output path for file formats; ignored for `POLARS` |
| `config` | `ExportConfig \| None` | `None` | Export configuration; a default `ExportConfig(format=format)` is used when `None` |

#### Returns

`ExportResult` — contains `success`, `metadata`, `file_path`, and `data` (populated for `POLARS` format).

#### Raises

| Exception | When |
|-----------|------|
| `ValueError` | `format` is not a registered format (e.g., `PARQUET`) |
| `RuntimeError` | Formatter raises an internal error |

#### Example

```python
from pathlib import Path
from tvkit.export import DataExporter, ExportConfig, ExportFormat

exporter = DataExporter()
config = ExportConfig(format=ExportFormat.JSON, timestamp_format="unix")
result = await exporter.export_ohlcv_data(
    bars,
    ExportFormat.JSON,
    file_path=Path("btc.json"),
    config=config,
)
print(result.success)     # True
print(result.file_path)   # PosixPath('btc.json')
```

---

### `export_scanner_data()`

Low-level export method for scanner data with full format and configuration control.

```python
async def export_scanner_data(
    self,
    data: list[StockData],
    format: ExportFormat,
    file_path: Path | str | None = None,
    config: ExportConfig | None = None,
) -> ExportResult: ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | `list[StockData]` | required | Scanner rows from `ScannerService.scan_market()` |
| `format` | `ExportFormat` | required | Target format |
| `file_path` | `Path \| str \| None` | `None` | Output path for file formats |
| `config` | `ExportConfig \| None` | `None` | Export configuration |

#### Returns

`ExportResult`

#### Raises

| Exception | When |
|-----------|------|
| `ValueError` | `format` is not registered |
| `RuntimeError` | Formatter error |

#### Example

```python
from tvkit.export import DataExporter, ExportFormat
from tvkit.api.scanner.markets import Market
from tvkit.api.scanner.models import ColumnSets, create_scanner_request
from tvkit.api.scanner.services import ScannerService

request = create_scanner_request(columns=ColumnSets.BASIC, range_end=100)
async with ScannerService() as service:
    response = await service.scan_market(Market.AMERICA, request)

exporter = DataExporter()
result = await exporter.export_scanner_data(
    response.data,
    ExportFormat.CSV,
    file_path="us_stocks.csv",
)
```

---

### `to_polars()`

Convenience method — exports directly to a Polars DataFrame without writing any file.

```python
async def to_polars(
    self,
    data: list[OHLCVBar] | list[StockData],
    add_analysis: bool = False,
) -> pl.DataFrame: ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | `list[OHLCVBar] \| list[StockData]` | required | OHLCV bars or scanner rows |
| `add_analysis` | `bool` | `False` | When `True` and data is `list[OHLCVBar]`, adds financial analysis columns (SMA, VWAP, etc.) to the DataFrame |

#### Returns

`pl.DataFrame` — the exported data as a Polars DataFrame.

#### Raises

| Exception | When |
|-----------|------|
| `RuntimeError` | Formatter error |

#### Example

```python
from tvkit.export import DataExporter

exporter = DataExporter()

# OHLCV → DataFrame with analysis columns
df = await exporter.to_polars(bars, add_analysis=True)
print(df.columns)

# Scanner → DataFrame
df = await exporter.to_polars(response.data)
print(df.head())
```

---

### `to_json()`

Convenience method — exports to a JSON file and returns the written file path.

```python
async def to_json(
    self,
    data: list[OHLCVBar] | list[StockData],
    file_path: Path | str,
    include_metadata: bool = True,
    **json_options: Any,
) -> Path: ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | `list[OHLCVBar] \| list[StockData]` | required | Data to export |
| `file_path` | `Path \| str` | required | Output JSON file path |
| `include_metadata` | `bool` | `True` | Embed export metadata in the JSON output |
| `**json_options` | `Any` | — | Additional options passed to the JSON formatter (e.g., `indent=4`) |

#### Returns

`Path` — resolved path of the written JSON file.

#### Raises

| Exception | When |
|-----------|------|
| `RuntimeError` | Export failed or formatter did not produce a file |

#### Example

```python
from tvkit.export import DataExporter

exporter = DataExporter()
path = await exporter.to_json(bars, "aapl.json", indent=2)
print(path)  # PosixPath('aapl.json')
```

---

### `to_csv()`

Convenience method — exports to a CSV file and returns the written file path. Also writes a metadata sidecar file (`<name>.metadata.txt`) when `include_metadata=True`.

```python
async def to_csv(
    self,
    data: list[OHLCVBar] | list[StockData],
    file_path: Path | str,
    include_metadata: bool = True,
    **csv_options: Any,
) -> Path: ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | `list[OHLCVBar] \| list[StockData]` | required | Data to export |
| `file_path` | `Path \| str` | required | Output CSV file path |
| `include_metadata` | `bool` | `True` | Write a `<filename>.metadata.txt` sidecar file alongside the CSV |
| `**csv_options` | `Any` | — | Additional options passed to the CSV formatter (e.g., `delimiter=";"`, `timestamp_format="iso"`) |

#### Returns

`Path` — resolved path of the written CSV file.

#### Raises

| Exception | When |
|-----------|------|
| `RuntimeError` | Export failed or formatter did not produce a file |

#### Example

```python
from tvkit.export import DataExporter

exporter = DataExporter()
path = await exporter.to_csv(bars, "aapl.csv", timestamp_format="iso")
# Writes: aapl.csv and aapl.csv.metadata.txt
```

---

### `add_formatter()`

Register a custom formatter or replace a built-in one.

```python
def add_formatter(
    self,
    format_type: ExportFormat,
    formatter_class: type[BaseFormatter],
) -> None: ...
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format_type` | `ExportFormat` | required | The format this formatter handles |
| `formatter_class` | `type[BaseFormatter]` | required | A class (not instance) extending `BaseFormatter` |

#### Example

```python
from tvkit.export import DataExporter, ExportFormat
from tvkit.export.formatters import BaseFormatter

class ParquetFormatter(BaseFormatter):
    ...  # custom implementation

exporter = DataExporter()
exporter.add_formatter(ExportFormat.PARQUET, ParquetFormatter)
# ExportFormat.PARQUET is now usable
```

---

### `get_supported_formats()`

Return the list of currently registered export formats.

```python
def get_supported_formats(self) -> list[ExportFormat]: ...
```

#### Returns

`list[ExportFormat]` — formats with a registered formatter. By default: `[ExportFormat.POLARS, ExportFormat.JSON, ExportFormat.CSV]`.

#### Example

```python
exporter = DataExporter()
print(exporter.get_supported_formats())
# [<ExportFormat.POLARS: 'polars'>, <ExportFormat.JSON: 'json'>, <ExportFormat.CSV: 'csv'>]

# Get format values as plain strings
print([f.value for f in exporter.get_supported_formats()])
# ['polars', 'json', 'csv']
```

---

## Supported Input Data

`DataExporter` accepts two tvkit data types across all export methods:

| Data Type | Source API | Typical Origin |
|-----------|-----------|----------------|
| `list[OHLCVBar]` | Chart OHLCV API | `get_historical_ohlcv()`, `get_ohlcv()` |
| `list[StockData]` | Scanner API | `ScannerService.scan_market()` |

The exporter detects the data type automatically based on the first element of the list. Passing an empty list is valid and produces an empty output.

> **Note:** All export methods are `async` to allow non-blocking file I/O and formatter processing. Use `await` for every call, including `to_polars()`.

---

## Type Definitions

### `ExportFormat`

```python
from tvkit.export import ExportFormat
```

`str` enum of export format identifiers.

| Member | Value | Registered by default | Notes |
|--------|-------|-----------------------|-------|
| `ExportFormat.POLARS` | `"polars"` | ✅ | Returns a `polars.DataFrame` in `result.data` |
| `ExportFormat.JSON` | `"json"` | ✅ | Writes a JSON file |
| `ExportFormat.CSV` | `"csv"` | ✅ | Writes a CSV file + optional `.metadata.txt` sidecar |
| `ExportFormat.PARQUET` | `"parquet"` | ❌ | Defined in enum but **not registered** — raises `ValueError` unless a custom formatter is added via `add_formatter()` |

---

### `ExportConfig`

```python
from tvkit.export import ExportConfig
```

Pydantic model controlling export behaviour. Pass to `export_ohlcv_data()` or `export_scanner_data()` for fine-grained control.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | `ExportFormat` | required | Export format |
| `file_path` | `Path \| None` | `None` | Output path; overridden by the `file_path` method argument if both are provided |
| `timestamp_format` | `str` | `"iso"` | Timestamp serialisation: `"iso"` (ISO 8601 string), `"unix"` (float seconds), or `"datetime"` (Python `datetime` object) |
| `include_metadata` | `bool` | `True` | Include metadata in the export output |
| `options` | `dict[str, Any]` | `{}` | Formatter-specific options (e.g., `{"add_analysis": True}` for Polars, `{"indent": 2}` for JSON) |

**Validation:** `timestamp_format` must be one of `"iso"`, `"unix"`, `"datetime"` — other values raise `ValueError`.

---

### `ExportResult`

```python
from tvkit.export import ExportResult
```

Returned by `export_ohlcv_data()` and `export_scanner_data()`.

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | `True` if export completed without error |
| `metadata` | `ExportMetadata` | Export metadata (timestamp, record count, format, etc.) |
| `file_path` | `Path \| None` | Written file path; `None` for `POLARS` format |
| `error_message` | `str \| None` | Error description when `success=False`; `None` otherwise |
| `data` | `Any \| None` | The exported data object for in-memory formats (`POLARS`); `None` for file formats |

---

### `ExportMetadata`

```python
from tvkit.export import ExportMetadata
```

Embedded in every `ExportResult` and written to sidecar files.

| Field | Type | Description |
|-------|------|-------------|
| `export_timestamp` | `datetime` | When the export ran (UTC) |
| `source` | `str` | Data source: `"ohlcv"` or `"scanner"` |
| `symbol` | `str \| None` | Symbol if applicable |
| `interval` | `str \| None` | Interval if applicable (OHLCV only) |
| `record_count` | `int` | Number of rows exported |
| `format` | `ExportFormat` | Format used |
| `file_path` | `str \| None` | Absolute path of the output file |

---

## Limits and Behaviour Notes

- `DataExporter` is stateless across exports — a single instance can be reused for many exports.
- `to_polars()`, `to_json()`, and `to_csv()` are thin wrappers around `export_ohlcv_data()` / `export_scanner_data()`. They detect the data type at runtime via `isinstance(data[0], OHLCVBar)`.
- Passing an empty list (`data=[]`) does not raise an error; it produces an empty DataFrame or an empty file with metadata.
- `ExportFormat.PARQUET` is defined in the enum for future use. Using it without registering a formatter raises `ValueError: Unsupported export format: parquet`.
- For large datasets, prefer `to_polars()` + downstream Polars operations over writing to CSV/JSON and re-reading, to avoid unnecessary I/O.

---

## See Also

- [Exporting Guide](../../guides/exporting.md)
- [Scanner Reference](../scanner/scanner.md)
- [Chart OHLCV Reference](../chart/ohlcv.md)
