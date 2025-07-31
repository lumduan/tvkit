# Data Exporter Methods

This document provides comprehensive usage documentation for all public methods in the Data Exporter module.

**Module**: `tvkit.export.data_exporter.py`

The Data Exporter provides a unified interface for exporting financial data from tvkit APIs to various formats including Polars DataFrames, JSON, and CSV files with extensive customization options.

## Table of Contents

- [Constructor](#constructor)
- [Core Export Methods](#core-export-methods)
- [Convenience Methods](#convenience-methods)
- [Formatter Management](#formatter-management)
- [Configuration and Examples](#configuration-and-examples)
- [Advanced Usage](#advanced-usage)

---

## Constructor

### `__init__()`

```python
def __init__(self) -> None
```

Initialize the DataExporter with available formatters for different export formats.

#### Parameters
- None

#### Returns
- None

#### Example
```python
from tvkit.export import DataExporter

exporter = DataExporter()
print(f"Supported formats: {[f.value for f in exporter.get_supported_formats()]}")
```

#### Example Output
```python
Supported formats: ['polars', 'json', 'csv']
```

---

## Core Export Methods

### `export_ohlcv_data()`

```python
async def export_ohlcv_data(
    self,
    data: List[OHLCVBar],
    format: ExportFormat,
    file_path: Optional[Union[Path, str]] = None,
    config: Optional[ExportConfig] = None,
) -> ExportResult
```

Export OHLCV data to the specified format with full configuration control and validation.

#### Parameters
- `data` (List[OHLCVBar]): List of OHLCV bars from tvkit chart API
- `format` (ExportFormat): Export format to use (POLARS, JSON, CSV)
- `file_path` (Optional[Union[Path, str]], optional): Optional file path for file-based exports
- `config` (Optional[ExportConfig], optional): Optional export configuration for customization

#### Returns
- `ExportResult`: ExportResult with operation details and exported data

#### Raises
- `ValueError`: If format is not supported or data is invalid

#### Example
```python
from tvkit.export import DataExporter, ExportFormat, ExportConfig
from tvkit.api.chart.ohlcv import OHLCV

async def export_btc_data():
    # Get OHLCV data
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("BINANCE:BTCUSDT", "1h", 100)
    
    exporter = DataExporter()
    
    # Export to Polars DataFrame with analysis
    config = ExportConfig(
        format=ExportFormat.POLARS,
        options={"add_analysis": True}
    )
    result = await exporter.export_ohlcv_data(bars, ExportFormat.POLARS, config=config)
    df = result.data
    print(f"DataFrame shape: {df.shape}")
    
    # Export to JSON file with custom formatting
    json_config = ExportConfig(
        format=ExportFormat.JSON,
        include_metadata=True,
        options={"indent": 4, "timestamp_format": "iso"}
    )
    json_result = await exporter.export_ohlcv_data(
        bars,
        ExportFormat.JSON,
        file_path="btc_hourly.json",
        config=json_config
    )
    print(f"JSON exported to: {json_result.file_path}")
    
    return result, json_result

# Usage
polars_result, json_result = await export_btc_data()
```

#### Example Output
```python
DataFrame shape: (100, 9)  # 6 OHLCV columns + 3 analysis columns
JSON exported to: btc_hourly.json

ExportResult(
    success=True,
    format=ExportFormat.POLARS,
    record_count=100,
    file_path=None,
    data=<polars.DataFrame shape=(100, 9)>,
    export_time=datetime.datetime(2024, 1, 15, 14, 30, 0),
    error_message=None
)
```

---

### `export_scanner_data()`

```python
async def export_scanner_data(
    self,
    data: List[StockData],
    format: ExportFormat,
    file_path: Optional[Union[Path, str]] = None,
    config: Optional[ExportConfig] = None,
) -> ExportResult
```

Export scanner data to the specified format with comprehensive stock information handling.

#### Parameters
- `data` (List[StockData]): List of scanner StockData from tvkit scanner API
- `format` (ExportFormat): Export format to use
- `file_path` (Optional[Union[Path, str]], optional): Optional file path for file-based exports
- `config` (Optional[ExportConfig], optional): Optional export configuration

#### Returns
- `ExportResult`: ExportResult with operation details and exported data

#### Example
```python
from tvkit.export import DataExporter, ExportFormat
from tvkit.api.scanner.services import ScannerService, create_comprehensive_request
from tvkit.api.scanner.markets import Market

async def export_market_data():
    # Get scanner data
    service = ScannerService()
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=50
    )
    response = await service.scan_market(Market.AMERICA, request)
    
    exporter = DataExporter()
    
    # Export to CSV with metadata
    csv_result = await exporter.export_scanner_data(
        response.data,
        ExportFormat.CSV,
        file_path="us_top50_stocks.csv"
    )
    
    print(f"Exported {csv_result.record_count} stocks to {csv_result.file_path}")
    
    # Export to Polars for analysis
    polars_result = await exporter.export_scanner_data(
        response.data,
        ExportFormat.POLARS
    )
    df = polars_result.data
    
    # Quick analysis
    print(f"Average market cap: ${df['market_cap_basic'].mean() / 1e9:.1f}B")
    print(f"Median P/E ratio: {df['pe_ratio'].median():.1f}")
    
    return csv_result, polars_result

# Usage
csv_result, polars_result = await export_market_data()
```

#### Example Output
```python
Exported 50 stocks to us_top50_stocks.csv
Average market cap: $845.3B
Median P/E ratio: 22.5

ExportResult(
    success=True,
    format=ExportFormat.CSV,
    record_count=50,
    file_path=Path("us_top50_stocks.csv"),
    data=None,
    export_time=datetime.datetime(2024, 1, 15, 14, 30, 0),
    error_message=None
)
```

---

## Convenience Methods

### `to_polars()`

```python
async def to_polars(
    self, 
    data: Union[List[OHLCVBar], List[StockData]], 
    add_analysis: bool = False
) -> Any
```

Convenience method to export data directly to Polars DataFrame with optional financial analysis features.

#### Parameters
- `data` (Union[List[OHLCVBar], List[StockData]]): OHLCV bars or scanner data
- `add_analysis` (bool, optional): Whether to add financial analysis columns (OHLCV only) (default: False)

#### Returns
- `Any`: Polars DataFrame with the exported data

#### Example
```python
from tvkit.export import DataExporter
from tvkit.api.chart.ohlcv import OHLCV

async def quick_polars_export():
    # Get some OHLCV data
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", 30)
    
    exporter = DataExporter()
    
    # Simple DataFrame export
    df_basic = await exporter.to_polars(bars)
    print("Basic columns:", df_basic.columns)
    
    # With technical analysis
    df_analysis = await exporter.to_polars(bars, add_analysis=True)
    print("Analysis columns:", df_analysis.columns)
    
    # Show recent data with analysis
    print("\nRecent AAPL data with analysis:")
    print(df_analysis.tail(5).select([
        "timestamp", "close", "volume", "sma_20", "vwap"
    ]))
    
    return df_basic, df_analysis

# Usage
df_basic, df_analysis = await quick_polars_export()
```

#### Example Output
```python
Basic columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
Analysis columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'sma_20', 'vwap', 'rsi']

Recent AAPL data with analysis:
┌────────────┬─────────┬──────────┬─────────────┬─────────────┐
│ timestamp  ┆ close   ┆ volume   ┆ sma_20      ┆ vwap        │
│ ---        ┆ ---     ┆ ---      ┆ ---         ┆ ---         │
│ i64        ┆ f64     ┆ f64      ┆ f64         ┆ f64         │
╞════════════╪═════════╪══════════╪═════════════╪═════════════╡
│ 1704326400 ┆ 185.42  ┆ 45000000 ┆ 182.15      ┆ 184.87      │
│ 1704412800 ┆ 186.18  ┆ 38000000 ┆ 182.68      ┆ 185.23      │
│ 1704499200 ┆ 187.35  ┆ 42000000 ┆ 183.22      ┆ 185.67      │
│ 1704585600 ┆ 188.12  ┆ 39000000 ┆ 183.85      ┆ 186.15      │
│ 1704672000 ┆ 189.45  ┆ 35000000 ┆ 184.52      ┆ 186.78      │
└────────────┴─────────┴──────────┴─────────────┴─────────────┘
```

---

### `to_json()`

```python
async def to_json(
    self,
    data: Union[List[OHLCVBar], List[StockData]],
    file_path: Union[Path, str],
    include_metadata: bool = True,
    **json_options: Any,
) -> Path
```

Convenience method to export data to JSON file with customizable formatting options.

#### Parameters
- `data` (Union[List[OHLCVBar], List[StockData]]): OHLCV bars or scanner data
- `file_path` (Union[Path, str]): Output file path
- `include_metadata` (bool, optional): Whether to include metadata in JSON (default: True)
- `**json_options` (Any): Additional JSON formatting options (indent, separators, etc.)

#### Returns
- `Path`: Path to the created JSON file

#### Example
```python
from tvkit.export import DataExporter
from tvkit.api.scanner.services import ScannerService
from tvkit.api.scanner.models import create_scanner_request, ColumnSets
from tvkit.api.scanner.markets import Market

async def export_to_json():
    # Get scanner data
    service = ScannerService()
    request = create_scanner_request(
        columns=ColumnSets.FUNDAMENTALS,
        range_end=10
    )
    response = await service.scan_market(Market.THAILAND, request)
    
    exporter = DataExporter()
    
    # Export with pretty formatting
    json_file = await exporter.to_json(
        response.data,
        "thai_stocks.json",
        include_metadata=True,
        indent=2,
        separators=(',', ': '),
        timestamp_format="iso"
    )
    
    print(f"✅ Exported to: {json_file}")
    
    # Read back and show structure
    import json
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    print(f"📊 Metadata: {data['metadata']}")
    print(f"📈 Data records: {len(data['data'])}")
    print(f"🏢 First stock: {data['data'][0]['name']}")
    
    return json_file

# Usage
json_path = await export_to_json()
```

#### Example Output
```python
✅ Exported to: thai_stocks.json
📊 Metadata: {
    'export_format': 'json',
    'record_count': 10,
    'export_time': '2024-01-15T14:30:00Z',
    'data_type': 'scanner'
}
📈 Data records: 10
🏢 First stock: AOT

Path("thai_stocks.json")

# File contents (sample):
{
  "metadata": {
    "export_format": "json",
    "record_count": 10,
    "export_time": "2024-01-15T14:30:00Z",
    "data_type": "scanner"
  },
  "data": [
    {
      "name": "AOT",
      "data": {
        "market_cap_basic": 125000000000,
        "close": 65.50,
        "volume": 2500000,
        "pe_ratio": 18.5,
        "dividend_yield": 0.045
      }
    },
    // ... more stocks
  ]
}
```

---

### `to_csv()`

```python
async def to_csv(
    self,
    data: Union[List[OHLCVBar], List[StockData]],
    file_path: Union[Path, str],
    include_metadata: bool = True,
    **csv_options: Any,
) -> Path
```

Convenience method to export data to CSV file with customizable formatting and metadata options.

#### Parameters
- `data` (Union[List[OHLCVBar], List[StockData]]): OHLCV bars or scanner data
- `file_path` (Union[Path, str]): Output file path
- `include_metadata` (bool, optional): Whether to include metadata file (default: True)
- `**csv_options` (Any): Additional CSV formatting options (delimiter, timestamp_format, etc.)

#### Returns
- `Path`: Path to the created CSV file

#### Example
```python
from tvkit.export import DataExporter
from tvkit.api.chart.ohlcv import OHLCV

async def export_to_csv():
    # Get OHLCV data
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("FOREX:EURUSD", "4h", 100)
    
    exporter = DataExporter()
    
    # Export with European CSV format
    csv_file = await exporter.to_csv(
        bars,
        "eurusd_4h_data.csv",
        include_metadata=True,
        delimiter=";",
        timestamp_format="iso",
        decimal_places=5
    )
    
    print(f"✅ Exported to: {csv_file}")
    
    # Show file info
    import os
    file_size = os.path.getsize(csv_file)
    print(f"📁 File size: {file_size:,} bytes")
    
    # Show first few lines
    with open(csv_file, 'r') as f:
        lines = f.readlines()[:5]
        print("📄 First 5 lines:")
        for line in lines:
            print(f"   {line.strip()}")
    
    return csv_file

# Usage
csv_path = await export_to_csv()
```

#### Example Output
```python
✅ Exported to: eurusd_4h_data.csv
📁 File size: 8,245 bytes
📄 First 5 lines:
   timestamp;open;high;low;close;volume
   2024-01-01T00:00:00Z;1.10250;1.10380;1.10180;1.10320;0.00000
   2024-01-01T04:00:00Z;1.10320;1.10450;1.10250;1.10390;0.00000
   2024-01-01T08:00:00Z;1.10390;1.10520;1.10340;1.10480;0.00000
   2024-01-01T12:00:00Z;1.10480;1.10550;1.10420;1.10510;0.00000

Path("eurusd_4h_data.csv")
```

---

## Formatter Management

### `add_formatter()`

```python
def add_formatter(
    self, 
    format_type: ExportFormat, 
    formatter_class: Type[BaseFormatter]
) -> None
```

Add or replace a formatter for a specific format, enabling custom export format support and extensibility.

#### Parameters
- `format_type` (ExportFormat): Export format type to register
- `formatter_class` (Type[BaseFormatter]): Formatter class that extends BaseFormatter

#### Returns
- None

#### Example
```python
from tvkit.export import DataExporter, BaseFormatter, ExportFormat, ExportResult
from tvkit.export.models import OHLCVExportData, ScannerExportData
from pathlib import Path
from typing import List, Optional, Union, Any
import pandas as pd

class PandasFormatter(BaseFormatter):
    """Custom formatter for Pandas DataFrames."""
    
    async def export_ohlcv(
        self, 
        data: List[OHLCVExportData], 
        file_path: Optional[Union[Path, str]] = None
    ) -> ExportResult:
        # Convert to pandas DataFrame
        df_data = [
            {
                "timestamp": item.timestamp,
                "open": item.open,
                "high": item.high,
                "low": item.low,
                "close": item.close,
                "volume": item.volume
            }
            for item in data
        ]
        
        df = pd.DataFrame(df_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        result_data = df
        result_file_path = None
        
        if file_path:
            # Save to Parquet for efficient storage
            parquet_path = Path(str(file_path).replace('.csv', '.parquet'))
            df.to_parquet(parquet_path)
            result_file_path = parquet_path
        
        return ExportResult(
            success=True,
            format=ExportFormat.PANDAS,  # Custom format
            record_count=len(data),
            file_path=result_file_path,
            data=result_data,
            export_time=datetime.now(),
        )
    
    async def export_scanner(
        self, 
        data: List[ScannerExportData], 
        file_path: Optional[Union[Path, str]] = None
    ) -> ExportResult:
        # Implementation for scanner data
        # ... similar to export_ohlcv
        pass

# Usage
from enum import Enum

class ExtendedExportFormat(Enum):
    POLARS = "polars"
    JSON = "json"
    CSV = "csv"
    PANDAS = "pandas"  # Custom format

exporter = DataExporter()
exporter.add_formatter(ExtendedExportFormat.PANDAS, PandasFormatter)

print("✅ Custom Pandas formatter added")
print(f"📊 Available formats: {[f.value for f in exporter.get_supported_formats()]}")
```

#### Example Output
```python
✅ Custom Pandas formatter added
📊 Available formats: ['polars', 'json', 'csv', 'pandas']
```

---

### `get_supported_formats()`

```python
def get_supported_formats(self) -> List[ExportFormat]
```

Get list of supported export formats available in the current DataExporter instance.

#### Parameters
- None

#### Returns
- `List[ExportFormat]`: List of supported ExportFormat values

#### Example
```python
from tvkit.export import DataExporter

def check_export_capabilities():
    exporter = DataExporter()
    
    formats = exporter.get_supported_formats()
    print("🚀 TVKit Data Exporter - Supported Formats:")
    print("=" * 45)
    
    format_descriptions = {
        "polars": "High-performance DataFrames with optional technical analysis",
        "json": "Structured JSON files with metadata and customizable formatting",
        "csv": "Comma-separated values with European formatting support"
    }
    
    for fmt in formats:
        description = format_descriptions.get(fmt.value, "Custom format")
        print(f"📊 {fmt.value.upper():8s} - {description}")
    
    print(f"\nTotal supported formats: {len(formats)}")
    return formats

# Usage
supported_formats = check_export_capabilities()
```

#### Example Output
```python
🚀 TVKit Data Exporter - Supported Formats:
=============================================
📊 POLARS   - High-performance DataFrames with optional technical analysis
📊 JSON     - Structured JSON files with metadata and customizable formatting
📊 CSV      - Comma-separated values with European formatting support

Total supported formats: 3
List[ExportFormat.POLARS, ExportFormat.JSON, ExportFormat.CSV]
```

---

## Configuration and Examples

### Advanced Configuration

```python
from tvkit.export import DataExporter, ExportConfig, ExportFormat
from tvkit.api.chart.ohlcv import OHLCV

async def advanced_export_configuration():
    # Get sample data
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("BINANCE:ETHUSDT", "1D", 50)
    
    exporter = DataExporter()
    
    # Polars with technical analysis
    polars_config = ExportConfig(
        format=ExportFormat.POLARS,
        include_metadata=True,
        options={
            "add_analysis": True,
            "sma_periods": [10, 20, 50],
            "include_rsi": True,
            "rsi_period": 14
        }
    )
    
    polars_result = await exporter.export_ohlcv_data(
        bars, 
        ExportFormat.POLARS, 
        config=polars_config
    )
    
    df = polars_result.data
    print(f"📊 Polars DataFrame: {df.shape}")
    print(f"📈 Columns: {df.columns}")
    
    # JSON with custom formatting
    json_config = ExportConfig(
        format=ExportFormat.JSON,
        include_metadata=True,
        options={
            "indent": 2,
            "separators": (',', ': '),
            "timestamp_format": "iso",
            "include_summary_stats": True
        }
    )
    
    json_result = await exporter.export_ohlcv_data(
        bars,
        ExportFormat.JSON,
        file_path="eth_daily_analysis.json",
        config=json_config
    )
    
    print(f"📄 JSON exported: {json_result.file_path}")
    
    return polars_result, json_result

# Usage
polars_result, json_result = await advanced_export_configuration()
```

---

## Advanced Usage

### Batch Export Pipeline

```python
from tvkit.export import DataExporter, ExportFormat
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.scanner.services import ScannerService, create_comprehensive_request
from tvkit.api.scanner.markets import Market
import asyncio
from pathlib import Path

async def batch_export_pipeline():
    """Complete pipeline for exporting multiple data types."""
    
    exporter = DataExporter()
    export_dir = Path("exports")
    export_dir.mkdir(exist_ok=True)
    
    results = {
        "ohlcv_exports": [],
        "scanner_exports": []
    }
    
    # OHLCV data for major cryptocurrencies
    crypto_symbols = [
        "BINANCE:BTCUSDT",
        "BINANCE:ETHUSDT", 
        "BINANCE:ADAUSDT",
        "BINANCE:SOLUSDT"
    ]
    
    print("🔄 Exporting OHLCV data for cryptocurrencies...")
    async with OHLCV() as client:
        for symbol in crypto_symbols:
            try:
                bars = await client.get_historical_ohlcv(symbol, "1D", 100)
                
                # Export to multiple formats
                symbol_name = symbol.split(':')[1].lower()
                
                # Polars with analysis
                polars_result = await exporter.to_polars(bars, add_analysis=True)
                
                # JSON export
                json_path = export_dir / f"{symbol_name}_daily.json"
                await exporter.to_json(bars, json_path, indent=2)
                
                # CSV export
                csv_path = export_dir / f"{symbol_name}_daily.csv"
                await exporter.to_csv(bars, csv_path, timestamp_format="iso")
                
                results["ohlcv_exports"].append({
                    "symbol": symbol,
                    "records": len(bars),
                    "polars_shape": polars_result.shape,
                    "json_path": json_path,
                    "csv_path": csv_path
                })
                
                print(f"✅ {symbol}: {len(bars)} bars exported")
                
            except Exception as e:
                print(f"❌ {symbol}: Error - {e}")
    
    # Scanner data for different markets
    markets = [Market.AMERICA, Market.THAILAND, Market.JAPAN]
    
    print("\n🔄 Exporting scanner data for markets...")
    service = ScannerService()
    
    for market in markets:
        try:
            request = create_comprehensive_request(
                sort_by="market_cap_basic",
                sort_order="desc",
                range_end=50
            )
            
            response = await service.scan_market(market, request)
            
            # Export to CSV
            csv_path = export_dir / f"{market.value}_top50.csv"
            await exporter.to_csv(response.data, csv_path)
            
            # Export to JSON
            json_path = export_dir / f"{market.value}_top50.json"
            await exporter.to_json(response.data, json_path, indent=2)
            
            results["scanner_exports"].append({
                "market": market.value,
                "records": len(response.data),
                "csv_path": csv_path,
                "json_path": json_path
            })
            
            print(f"✅ {market.value}: {len(response.data)} stocks exported")
            
        except Exception as e:
            print(f"❌ {market.value}: Error - {e}")
    
    # Summary
    print(f"\n📊 Export Summary:")
    print(f"   OHLCV exports: {len(results['ohlcv_exports'])}")
    print(f"   Scanner exports: {len(results['scanner_exports'])}")
    print(f"   Export directory: {export_dir.absolute()}")
    
    return results

# Usage
results = await batch_export_pipeline()
```

### Performance Monitoring

```python
import time
from typing import Dict, Any
from tvkit.export import DataExporter, ExportFormat

async def performance_benchmark():
    """Benchmark different export formats and configurations."""
    
    # Get test data
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv("BINANCE:BTCUSDT", "1h", 1000)
    
    exporter = DataExporter()
    benchmarks: Dict[str, Dict[str, Any]] = {}
    
    # Test configurations
    test_configs = [
        ("polars_basic", ExportFormat.POLARS, {"add_analysis": False}),
        ("polars_analysis", ExportFormat.POLARS, {"add_analysis": True}),
        ("json_compact", ExportFormat.JSON, {"indent": None}),
        ("json_pretty", ExportFormat.JSON, {"indent": 4}),
        ("csv_basic", ExportFormat.CSV, {"delimiter": ","}),
        ("csv_european", ExportFormat.CSV, {"delimiter": ";", "timestamp_format": "iso"})
    ]
    
    print("🏃‍♂️ Running export performance benchmarks...")
    print("=" * 60)
    
    for test_name, export_format, options in test_configs:
        start_time = time.time()
        
        try:
            if export_format == ExportFormat.POLARS:
                result = await exporter.to_polars(bars, **options)
                data_size = result.estimated_size("mb") if hasattr(result, 'estimated_size') else 0
            else:
                file_path = f"benchmark_{test_name}.{export_format.value}"
                if export_format == ExportFormat.JSON:
                    result_path = await exporter.to_json(bars, file_path, **options)
                else:  # CSV
                    result_path = await exporter.to_csv(bars, file_path, **options)
                
                # Get file size
                data_size = result_path.stat().st_size / (1024 * 1024)  # MB
            
            elapsed_time = time.time() - start_time
            
            benchmarks[test_name] = {
                "format": export_format.value,
                "time_seconds": elapsed_time,
                "data_size_mb": data_size,
                "records_per_second": len(bars) / elapsed_time,
                "success": True
            }
            
            print(f"✅ {test_name:15s}: {elapsed_time:.3f}s, {data_size:.2f}MB, {len(bars)/elapsed_time:.0f} rec/s")
            
        except Exception as e:
            benchmarks[test_name] = {
                "format": export_format.value,
                "time_seconds": 0,
                "data_size_mb": 0,
                "records_per_second": 0,
                "success": False,
                "error": str(e)
            }
            print(f"❌ {test_name:15s}: Error - {e}")
    
    # Performance summary
    successful_benchmarks = {k: v for k, v in benchmarks.items() if v["success"]}
    
    if successful_benchmarks:
        fastest = min(successful_benchmarks.items(), key=lambda x: x[1]["time_seconds"])
        smallest = min(successful_benchmarks.items(), key=lambda x: x[1]["data_size_mb"])
        
        print(f"\n🏆 Performance Summary:")
        print(f"   Fastest: {fastest[0]} ({fastest[1]['time_seconds']:.3f}s)")
        print(f"   Smallest: {smallest[0]} ({smallest[1]['data_size_mb']:.2f}MB)")
        print(f"   Total records: {len(bars):,}")
    
    return benchmarks

# Usage
benchmarks = await performance_benchmark()
```

These comprehensive examples demonstrate the full power and flexibility of the DataExporter class for handling various financial data export scenarios with performance optimization and extensive customization options.