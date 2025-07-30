# 📖 tvkit Documentation

Welcome to the **tvkit** documentation! This library provides comprehensive access to TradingView's financial data APIs with modern Python features.

## 📑 Documentation Structure

### Getting Started
- **[Quick Start Guide](quick-start.md)** - Get up and running in 5 minutes
- **[Installation](quick-start.md#installation)** - Installation methods and requirements

### Core Features
- **[Real-time Streaming](realtime_streaming.md)** - WebSocket streaming for live market data
- **[Data Export System](export_system.md)** - Multi-format data export capabilities
- **[Polars Integration](POLARS_INTEGRATION.md)** - High-performance data processing

### API Reference
- **[Chart API](api/chart.md)** - Real-time OHLCV and quote data
- **[Scanner API](api/scanner.md)** - Stock screening and fundamental analysis
- **[Export API](api/export.md)** - Data export configuration and methods

### Advanced Topics
- **[Error Handling](advanced/error_handling.md)** - Robust error handling patterns
- **[Performance Tips](advanced/performance.md)** - Optimization guidelines
- **[Testing](advanced/testing.md)** - Testing strategies and examples

## 🚀 Quick Examples

### Real-time Data Streaming
```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def stream_data():
    async with OHLCV() as client:
        async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="1"):
            print(f"BTC: ${bar.close} | Volume: {bar.volume}")

asyncio.run(stream_data())
```

### Data Export & Analysis
```python
from tvkit.export import DataExporter, ExportFormat

# Export to multiple formats
exporter = DataExporter()
await exporter.to_polars(bars, add_analysis=True)  # DataFrame with indicators
await exporter.to_json(bars, "data.json")         # JSON format
await exporter.to_csv(bars, "data.csv")           # CSV format
```

## 🏗️ Architecture Overview

**tvkit** follows a modular architecture with three main components:

1. **📡 Chart API**: Real-time WebSocket streaming for live market data
2. **🔍 Scanner API**: Advanced stock screening with 100+ financial metrics  
3. **💾 Export System**: Multi-format data export with technical analysis

## 🔗 External Resources

- **[GitHub Repository](https://github.com/lumduan/tvkit)** - Source code and issues
- **[PyPI Package](https://pypi.org/project/tvkit/)** - Package installation
- **[TradingView](https://www.tradingview.com/)** - Official TradingView platform

## 🤝 Contributing

We welcome contributions! Please see our [contributing guidelines](../README.md#contributing) for more information.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.