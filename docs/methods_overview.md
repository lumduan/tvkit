# TVKit Methods Documentation

This documentation provides comprehensive usage guides for all public methods in the key tvkit modules. Each module has its own dedicated documentation file with detailed examples, parameters, and real-world usage scenarios.

## 📚 Documentation Structure

### [OHLCV Client Methods](ohlcv_methods.md)
**Module**: `tvkit.api.chart.ohlcv.py`

Real-time and historical market data streaming client for TradingView's WebSocket API.

**Key Methods**:
- `get_ohlcv()` - Real-time OHLCV streaming
- `get_historical_ohlcv()` - Historical data retrieval  
- `get_quote_data()` - Quote data streaming
- `get_ohlcv_raw()` - Raw WebSocket data access
- `get_latest_trade_info()` - Multi-symbol trading information

**Best For**: Live market data streaming, historical price analysis, real-time trading applications

---

### [Scanner Service Methods](scanner_service_methods.md)
**Module**: `tvkit.api.scanner.services.scanner_service.py`

Market scanning and stock screening service with comprehensive filtering capabilities.

**Key Methods**:
- `scan_market()` - Market scanning with Market enum
- `scan_market_by_id()` - Market scanning with string identifiers
- `create_comprehensive_request()` - Full-featured scanner requests

**Best For**: Stock screening, market analysis, fundamental research, multi-market comparison

---

### [Data Exporter Methods](data_exporter_methods.md)
**Module**: `tvkit.export.data_exporter.py`

Unified data export interface supporting multiple formats with extensive customization.

**Key Methods**:
- `export_ohlcv_data()` - Export OHLCV data with full configuration
- `export_scanner_data()` - Export scanner results with formatting options
- `to_polars()` - Quick Polars DataFrame export
- `to_json()` - JSON file export with metadata
- `to_csv()` - CSV file export with formatting options

**Best For**: Data analysis workflows, report generation, format conversion, data persistence

---

## 🚀 Quick Start Examples

### Real-time Market Data
```python
from tvkit.api.chart.ohlcv import OHLCV

async with OHLCV() as client:
    async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="5m"):
        print(f"BTC: ${bar.close}, Volume: {bar.volume}")
```

### Market Scanning
```python
from tvkit.api.scanner.services import ScannerService, create_comprehensive_request
from tvkit.api.scanner.markets import Market

service = ScannerService()
request = create_comprehensive_request(sort_by="market_cap_basic", sort_order="desc")
response = await service.scan_market(Market.AMERICA, request)
```

### Data Export
```python
from tvkit.export import DataExporter, ExportFormat

exporter = DataExporter()
df = await exporter.to_polars(ohlcv_bars, add_analysis=True)
await exporter.to_json(scanner_data, "stocks.json", indent=2)
```

---

## 🛠️ Common Patterns

### Async Context Management
All tvkit services support async context managers for automatic resource cleanup:

```python
async with OHLCV() as client:
    # WebSocket connections automatically managed
    data = await client.get_historical_ohlcv("NASDAQ:AAPL", bars_count=10)

async with ScannerService() as service:
    # HTTP client resources automatically managed
    response = await service.scan_market(Market.THAILAND, request)
```

### Error Handling
Structured exception hierarchy for clear error handling:

```python
from tvkit.api.scanner.services import (
    ScannerConnectionError, 
    ScannerAPIError, 
    ScannerValidationError
)

try:
    response = await service.scan_market(Market.AMERICA, request)
except ScannerConnectionError as e:
    print(f"Connection failed: {e}")
except ScannerAPIError as e:
    print(f"API error: {e}")
except ScannerValidationError as e:
    print(f"Invalid response: {e}")
```

### Configuration Objects
Use configuration objects for advanced customization:

```python
from tvkit.export import ExportConfig, ExportFormat

config = ExportConfig(
    format=ExportFormat.JSON,
    include_metadata=True,
    options={"indent": 4, "timestamp_format": "iso"}
)

result = await exporter.export_ohlcv_data(bars, ExportFormat.JSON, config=config)
```

---

## 📊 Data Flow Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   OHLCV Client  │    │  Scanner Service │    │  Data Exporter  │
│                 │    │                  │    │                 │
│ • Real-time     │    │ • Market scans   │    │ • Polars        │
│ • Historical    │    │ • Stock filters  │    │ • JSON          │
│ • Quote data    │    │ • Fundamentals   │    │ • CSV           │
│ • Multi-symbol  │    │ • Technical data │    │ • Custom        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │    Unified Data Models    │
                    │                           │
                    │ • OHLCVBar               │
                    │ • StockData              │
                    │ • ScannerResponse        │
                    │ • ExportResult           │
                    └───────────────────────────┘
```

---

## 🎯 Use Case Matrix

| Use Case | Primary Module | Secondary Module | Example |
|----------|----------------|------------------|---------|
| **Live Trading** | OHLCV Client | Data Exporter | Real-time price feeds with CSV logging |
| **Stock Screening** | Scanner Service | Data Exporter | Filter stocks by P/E ratio, export to JSON |
| **Technical Analysis** | OHLCV Client | Data Exporter | Historical data with technical indicators |
| **Market Research** | Scanner Service | OHLCV Client | Fundamental screening + price validation |
| **Portfolio Analysis** | All Modules | - | Multi-asset data collection and analysis |
| **Reporting** | Data Exporter | Scanner Service | Automated market reports in multiple formats |

---

## 🔧 Advanced Integration

### Multi-Module Workflows
Combine multiple modules for comprehensive analysis:

```python
async def comprehensive_analysis(symbol: str):
    # 1. Get historical price data
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(symbol, interval="1D", bars_count=100)
    
    # 2. Get fundamental data via scanner
    service = ScannerService()
    # ... scanner logic for fundamental data
    
    # 3. Export combined analysis
    exporter = DataExporter()
    analysis_df = await exporter.to_polars(bars, add_analysis=True)
    
    # 4. Generate reports
    await exporter.to_json(combined_data, "analysis_report.json")
    
    return analysis_df
```

### Performance Optimization
Best practices for high-performance applications:

```python
# Batch operations
symbols = ["AAPL", "GOOGL", "MSFT", "AMZN"]
tasks = [client.get_historical_ohlcv(f"NASDAQ:{s}", bars_count=100) for s in symbols]
results = await asyncio.gather(*tasks)

# Efficient export configurations
config = ExportConfig(
    format=ExportFormat.POLARS,
    options={"add_analysis": False}  # Skip heavy computations if not needed
)
```

---

## 📖 Additional Resources

- **[OHLCV Methods](ohlcv_methods.md)** - Complete OHLCV client documentation
- **[Scanner Methods](scanner_service_methods.md)** - Comprehensive scanner service guide  
- **[Export Methods](data_exporter_methods.md)** - Full data export capabilities
- **Main README** - Project overview and installation
- **Examples Directory** - Working code examples and notebooks

---

## 🤝 Support and Feedback

Each documentation file includes:
- ✅ Complete method signatures with type hints
- 📝 Detailed parameter descriptions  
- 🔧 Real-world usage examples
- 📊 Realistic output samples
- ⚠️ Error handling patterns
- 🚀 Performance optimization tips

For questions or issues, refer to the specific method documentation or check the examples directory for working implementations.