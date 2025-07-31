# 📈 tvkit

Modern Python library for TradingView financial data APIs with comprehensive real-time streaming and export capabilities

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Async/Await](https://img.shields.io/badge/async-await-green.svg)](https://docs.python.org/3/library/asyncio.html)
[![Type Safety](https://img.shields.io/badge/typed-pydantic-red.svg)](https://pydantic.dev/)
[![Data Processing](https://img.shields.io/badge/powered%20by-polars-orange.svg)](https://pola.rs/)

**tvkit** is a comprehensive Python library for accessing TradingView's financial data APIs. It provides real-time market data streaming, comprehensive stock analysis, and powerful export capabilities with modern async-first architecture.

## ✨ Key Features

- 🚀 **Real-time Data Streaming**: WebSocket-based streaming for live market data
- 📊 **Multi-format Export**: Support for Polars DataFrames, JSON, CSV, and Parquet
- 🔍 **Multi-Market Scanner**: Screen 69 global markets with 101+ financial metrics
- ⚡ **High Performance**: Built with Polars for fast data processing
- 🛡️ **Type Safety**: Full Pydantic validation and type hints
- 🔄 **Async-First**: Modern async/await patterns throughout
- 🌍 **Global Markets**: Support for stocks, crypto, forex, and commodities
- 📈 **Technical Analysis**: Built-in indicators and financial calculations

## 🚀 Quick Start

### Installation

```bash
# Using uv (recommended)
uv add tvkit

# Using pip
pip install tvkit

# For development with pip (alternative to uv)
pip install -r requirements.txt
```

### Real-time Data Streaming

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def stream_data():
    async with OHLCV() as client:
        # Stream real-time OHLCV data
        async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="1"):
            print(f"BTC: ${bar.close} | Volume: {bar.volume}")

asyncio.run(stream_data())
```

### Data Export & Analysis

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter, ExportFormat

async def export_analysis():
    # Fetch historical data
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(
            "BINANCE:BTCUSDT",
            interval="60",
            bars_count=100
        )

    # Export to multiple formats
    exporter = DataExporter()

    # Export to Polars DataFrame with technical analysis
    df = await exporter.to_polars(bars, add_analysis=True)
    print(f"DataFrame: {len(df)} rows × {len(df.columns)} columns")

    # Export to files
    await exporter.to_json(bars, "btc_data.json")
    await exporter.to_csv(bars, "btc_data.csv")

asyncio.run(export_analysis())
```

## 🏗️ Architecture

**tvkit** is built with three main components:

### 1. 📡 Real-Time Chart API (`tvkit.api.chart`)

- **WebSocket Streaming**: Live market data with minimal latency
- **OHLCV Data**: Open, High, Low, Close, Volume with timestamps
- **Quote Data**: Real-time price updates and market information
- **Multiple Symbols**: Stream data from multiple assets simultaneously

```python
from tvkit.api.chart.ohlcv import OHLCV

# Stream multiple symbols
async with OHLCV() as client:
    symbols = ["BINANCE:BTCUSDT", "NASDAQ:AAPL", "FOREX:EURUSD"]
    async for info in client.get_latest_trade_info(symbols):
        print(f"Trade info: {info}")
```

### 2. 🔍 Scanner API (`tvkit.api.scanner`)

- **Multi-Market Scanning**: Access 69 global markets across 6 regions with unified API
- **Comprehensive Data**: 101+ financial columns including fundamentals, technicals, and valuation metrics
- **Advanced Screening**: Filter stocks by market cap, P/E ratios, ROE, dividends, volatility, and technical indicators
- **Regional Analysis**: Scan markets by region (Asia Pacific, Europe, North America, etc.)
- **Flexible Access**: Use Market enums or string IDs for dynamic market selection

```python
from tvkit.api.scanner import ScannerService, Market, MarketRegion
from tvkit.api.scanner import create_comprehensive_request, ColumnSets, get_markets_by_region

# Multi-market scanning example
async def scan_markets():
    service = ScannerService()
    
    # Comprehensive scan with all available data
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=50
    )
    
    # Scan specific markets
    thailand_data = await service.scan_market(Market.THAILAND, request)
    japan_data = await service.scan_market(Market.JAPAN, request)
    
    # Scan by market ID string
    brazil_data = await service.scan_market_by_id("brazil", request)
    
    # Regional scanning - get all Asia Pacific markets
    asia_markets = get_markets_by_region(MarketRegion.ASIA_PACIFIC)
    for market in asia_markets[:5]:  # Top 5 Asian markets
        response = await service.scan_market(market, request)
        print(f"{market.value}: {len(response.data)} stocks")

# Basic scanning with focused data
basic_request = create_scanner_request(
    columns=ColumnSets.FUNDAMENTALS,  # P/E, market cap, sector, etc.
    sort_by="market_cap_basic",
    sort_order="desc",
    range_end=100
)
```

### 3. 💾 Data Export System (`tvkit.export`)

- **Multiple Formats**: Polars DataFrames, JSON, CSV, Parquet
- **Financial Analysis**: Automatic calculation of technical indicators
- **Flexible Configuration**: Customizable export options and metadata
- **High Performance**: Optimized for large datasets

```python
from tvkit.export import DataExporter, ExportConfig, ExportFormat

# Advanced export configuration
config = ExportConfig(
    format=ExportFormat.CSV,
    timestamp_format="iso",
    include_metadata=True,
    options={"delimiter": ";", "include_headers": True}
)

exporter = DataExporter()
result = await exporter.export_ohlcv_data(bars, ExportFormat.CSV, config=config)
```

## 📊 Supported Data Types

### Financial Metrics (Scanner API) - 101+ Columns Available

| Category | Column Sets | Examples |
|----------|-------------|----------|
| **Price Data** | `BASIC`, `TECHNICAL` | Current price, change, volume, market cap, high/low/open |
| **Valuation Ratios** | `VALUATION`, `FUNDAMENTALS` | P/E ratio, P/B ratio, EV/Revenue, PEG ratio, Price/Sales |
| **Profitability** | `PROFITABILITY`, `COMPREHENSIVE` | ROE, ROA, gross/operating/net margins, EBITDA |
| **Financial Health** | `FINANCIAL_STRENGTH` | Debt/equity, current ratio, quick ratio, free cash flow |
| **Dividends** | `DIVIDENDS`, `FUNDAMENTALS` | Current yield, payout ratio, growth rate, continuous growth |
| **Performance** | `PERFORMANCE`, `DETAILED` | YTD, 1M, 3M, 6M, 1Y, 5Y, 10Y returns, volatility metrics |
| **Technical Indicators** | `TECHNICAL_INDICATORS` | RSI, MACD, Stochastic, CCI, momentum, recommendations |
| **Cash Flow** | `CASH_FLOW`, `COMPREHENSIVE_FULL` | Operating/investing/financing activities, free cash flow margin |
| **Balance Sheet** | `FINANCIAL_STRENGTH`, `COMPREHENSIVE_FULL` | Total assets/liabilities, debt ratios, cash positions |

### Global Market Coverage (Scanner API)

| Region | Markets | Examples |
|--------|---------|----------|
| **North America** | 2 markets | USA (NASDAQ, NYSE), Canada (TSX, TSXV) |
| **Europe** | 30 markets | Germany, France, UK, Netherlands, Switzerland, Italy |
| **Asia Pacific** | 17 markets | Japan, Thailand, Singapore, Korea, Australia, India, China |
| **Middle East & Africa** | 12 markets | UAE, Saudi Arabia, Israel, South Africa |
| **Latin America** | 7 markets | Brazil, Mexico, Argentina, Chile, Colombia |

### Market Data (Chart API)

- **OHLCV Bars**: Complete candlestick data with volume
- **Quote Data**: Real-time price feeds and market status
- **Trade Information**: Latest trades, price changes, volumes
- **Multiple Timeframes**: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, 1M

## 🔧 Advanced Usage

### Multi-Market Scanner Analysis

```python
import asyncio
from tvkit.api.scanner import ScannerService, Market, MarketRegion
from tvkit.api.scanner import create_comprehensive_request, get_markets_by_region

async def comprehensive_market_analysis():
    service = ScannerService()
    
    # Create comprehensive request with all financial metrics
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=10  # Top 10 stocks per market
    )
    
    # Regional analysis - scan all Asia Pacific markets
    asia_pacific_markets = get_markets_by_region(MarketRegion.ASIA_PACIFIC)
    market_leaders = {}
    
    for market in asia_pacific_markets[:6]:  # Top 6 Asian markets
        try:
            response = await service.scan_market(market, request)
            if response.data:
                top_stock = response.data[0]  # Market leader by market cap
                market_leaders[market.value] = {
                    'symbol': top_stock.name,
                    'price': f"{top_stock.close} {top_stock.currency}",
                    'market_cap': f"${top_stock.market_cap_basic:,.0f}" if top_stock.market_cap_basic else "N/A",
                    'pe_ratio': f"{top_stock.price_earnings_ttm:.2f}" if top_stock.price_earnings_ttm else "N/A",
                    'sector': top_stock.sector or "N/A"
                }
        except Exception as e:
            print(f"Error scanning {market.value}: {e}")
    
    # Display market leaders
    for market, data in market_leaders.items():
        print(f"{market.title()}: {data['symbol']} - {data['price']} "
              f"(Market Cap: {data['market_cap']}, P/E: {data['pe_ratio']})")

# Run analysis
asyncio.run(comprehensive_market_analysis())
```

### Custom Financial Analysis

```python
import polars as pl
from tvkit.export import DataExporter

# Get data and convert to Polars DataFrame
exporter = DataExporter()
df = await exporter.to_polars(ohlcv_bars, add_analysis=True)

# Advanced analysis with Polars
analysis_df = df.with_columns([
    # Bollinger Bands
    (pl.col("sma_20") + 2 * pl.col("close").rolling_std(20)).alias("bb_upper"),
    (pl.col("sma_20") - 2 * pl.col("close").rolling_std(20)).alias("bb_lower"),

    # Volume analysis
    (pl.col("volume") / pl.col("volume").rolling_mean(10)).alias("volume_ratio"),

    # Price momentum
    (pl.col("close") - pl.col("close").shift(5)).alias("momentum_5"),
])

# Export enhanced analysis
analysis_df.write_parquet("enhanced_analysis.parquet")
```

### Error Handling & Retry Logic

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def robust_streaming():
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            async with OHLCV() as client:
                async for bar in client.get_ohlcv("BINANCE:BTCUSDT"):
                    print(f"Price: ${bar.close}")

        except Exception as e:
            retry_count += 1
            wait_time = 2 ** retry_count  # Exponential backoff
            print(f"Error: {e}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
        else:
            break
```

### Multiple Symbol Monitoring

```python
async def monitor_portfolio():
    symbols = [
        "BINANCE:BTCUSDT",    # Cryptocurrency
        "NASDAQ:AAPL",        # US Stock
        "FOREX:EURUSD",       # Forex
        "OANDA:XAUUSD"        # Commodities (Gold)
    ]

    async with OHLCV() as client:
        async for trade_info in client.get_latest_trade_info(symbols):
            # Process multi-asset trade information
            print(f"Portfolio update: {trade_info}")
```

## 📦 Dependencies

**tvkit** uses modern, high-performance libraries:

- **[Polars](https://pola.rs/)** (≥1.0.0): Fast DataFrame operations
- **[Pydantic](https://pydantic.dev/)** (≥2.11.7): Data validation and settings
- **[websockets](https://websockets.readthedocs.io/)** (≥13.0): Async WebSocket client
- **[httpx](https://www.python-httpx.org/)** (≥0.28.0): Async HTTP client
- **Python 3.13+**: Modern async/await support

## 🏃‍♂️ Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/lumduan/tvkit.git
cd tvkit

# Install with uv (recommended)
uv sync

# Alternative: Install with pip
pip install -r requirements.txt
pip install mypy>=1.17.0  # For type checking

# Run tests
uv run python -m pytest tests/ -v
# Or with pip: python -m pytest tests/ -v

# Type checking
uv run mypy tvkit/
# Or with pip: mypy tvkit/

# Code formatting
uv run ruff format .
uv run ruff check .
# Or with pip: ruff format . && ruff check .
```

### Running Examples

```bash
# Real-time streaming example
uv run python examples/realtime_streaming_example.py
# Or with pip: python examples/realtime_streaming_example.py

# Export functionality demo
uv run python examples/export_demo.py
# Or with pip: python examples/export_demo.py

# Polars financial analysis
uv run python examples/polars_financial_analysis.py
# Or with pip: python examples/polars_financial_analysis.py
```

## 📖 Documentation

- **[Real-time Streaming Guide](docs/realtime_streaming.md)**: WebSocket streaming documentation
- **[Polars Integration](docs/POLARS_INTEGRATION.md)**: Data processing and analysis
- **[API Reference](https://github.com/lumduan/tvkit#readme)**: Complete API documentation

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. **Fork** the repository
2. **Create** a feature branch
3. **Add** tests for new functionality
4. **Ensure** all quality checks pass:

   ```bash
   # With uv
   uv run ruff check . && uv run ruff format . && uv run mypy tvkit/
   uv run python -m pytest tests/ -v

   # Or with pip
   ruff check . && ruff format . && mypy tvkit/
   python -m pytest tests/ -v
   ```

5. **Submit** a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Homepage**: [https://github.com/lumduan/tvkit](https://github.com/lumduan/tvkit)
- **Documentation**: [https://github.com/lumduan/tvkit#readme](https://github.com/lumduan/tvkit#readme)
- **Bug Reports**: [https://github.com/lumduan/tvkit/issues](https://github.com/lumduan/tvkit/issues)
- **PyPI Package**: [https://pypi.org/project/tvkit/](https://pypi.org/project/tvkit/)

## ⭐ Support

If you find **tvkit** useful, please consider giving it a star on GitHub! Your support helps us continue developing and improving the library.

---

Built with ❤️ for the financial data community
