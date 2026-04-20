# API Reference

Complete reference for every public class, method, and type in tvkit. Each page documents one module: signatures, parameter tables, return types, exceptions, and usage examples.

The reference is organized by module, matching the structure of the `tvkit` package.

For narrative guides and integration walk-throughs, see [Guides](../guides/).
For conceptual background, see [Concepts](../concepts/).

---

## Package Structure

```
tvkit
├── api.chart
│   ├── OHLCV          → async WebSocket client
│   └── utils          → timestamp, interval, range helpers
├── api.scanner
│   ├── ScannerService → market screening client
│   └── markets        → 69 global market identifiers
└── export
    └── DataExporter   → Polars, JSON, CSV export
```

---

## Chart API — `tvkit.api.chart`

Async clients for real-time and historical OHLCV data via TradingView's WebSocket protocol.

| Page | Class / Module | What it covers |
|------|---------------|----------------|
| [OHLCV Client](chart/ohlcv.md) | `OHLCV` | Async WebSocket client — `get_historical_ohlcv()`, `get_ohlcv()`, `get_quote_data()`, `get_ohlcv_raw()`, `get_latest_trade_info()` |
| [Chart Utilities](chart/utils.md) | `tvkit.api.chart.utils` | `to_unix_timestamp()`, `end_of_day_timestamp()`, `validate_interval()`, `build_range_param()` — synchronous helper functions used internally by the OHLCV client and available for external use |

---

## Scanner API — `tvkit.api.scanner`

Global stock screening across 69 markets with 100+ financial data columns.

| Page | Class / Module | What it covers |
|------|---------------|----------------|
| [Scanner](scanner/scanner.md) | `ScannerService` | `scan_market()`, `scan_market_by_id()`, `create_scanner_request()`, `create_comprehensive_request()`, column sets, `ScannerRequest`, `StockData`, exception hierarchy |
| [Markets](scanner/markets.md) | `Market`, `MarketRegion` | 69 global market identifiers, 6 regional groupings, `MarketInfo`, `get_market_info()`, `get_markets_by_region()`, `is_valid_market()`, `get_all_markets()` |

---

## Export API — `tvkit.export`

Multi-format data export for OHLCV and scanner results.

| Page | Class / Module | What it covers |
|------|---------------|----------------|
| [DataExporter](export/exporter.md) | `DataExporter` | `export_ohlcv_data()`, `export_scanner_data()`, `to_polars()`, `to_json()`, `to_csv()`, `add_formatter()`, `get_supported_formats()`, `ExportFormat`, `ExportConfig`, `ExportResult`, `ExportMetadata` |

---

---

## Batch API — `tvkit.batch`

High-throughput async batch downloader for large symbol sets.

| Page | Class / Module | What it covers |
|------|---------------|----------------|
| [Batch Downloader](batch/downloader.md) | `batch_download`, `BatchDownloadRequest` | `batch_download()`, `BatchDownloadRequest`, `BatchDownloadSummary`, `SymbolResult`, `ErrorInfo`, `BatchDownloadError`, retry policy, pre-flight validation, deduplication |

---

## Quick Navigation: which page do I need?

| I want to… | Go to |
|-----------|-------|
| Fetch historical OHLCV bars | [OHLCV Client](chart/ohlcv.md) |
| Stream real-time price updates | [OHLCV Client](chart/ohlcv.md) |
| Fetch historical bars for many symbols concurrently | [Batch Downloader](batch/downloader.md) |
| Validate or convert an interval string | [Chart Utilities](chart/utils.md) |
| Screen stocks with filters and sorting | [Scanner](scanner/scanner.md) |
| Find the market identifier for a country or exchange | [Markets](scanner/markets.md) |
| Export data to a Polars DataFrame | [DataExporter](export/exporter.md) |
| Export data to CSV or JSON | [DataExporter](export/exporter.md) |
| Register a custom export formatter | [DataExporter](export/exporter.md) |
