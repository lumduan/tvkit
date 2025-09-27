# 📈 tvkit

Modern Python library for TradingView financial data APIs with comprehensive real-time streaming and export capabilities

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
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

### 🏃‍♂️ Super Quick Start (2 minutes)

**Try TVKit instantly:**

```bash
# Install and test in one command
pip install tvkit && python -c "import tvkit; print(tvkit.run_async(tvkit.get_stock_price('NASDAQ:AAPL')))"

# Or with uv (recommended)
uv add tvkit && uv run python -c "import tvkit; print(tvkit.run_async(tvkit.get_stock_price('NASDAQ:AAPL')))"
```

**One-liner examples:**

```python
# Get Apple's current price
import tvkit; print(f"Apple: ${tvkit.run_async(tvkit.get_stock_price('NASDAQ:AAPL'))['price']}")

# Compare tech stocks
import tvkit; print(tvkit.run_async(tvkit.compare_stocks(['NASDAQ:AAPL', 'NASDAQ:GOOGL'])))

# Get crypto prices
import tvkit; print(tvkit.run_async(tvkit.get_crypto_prices(3)))

# Access macro liquidity indicators (INDEX:NDFI, USI:PCC)
from tvkit.api.chart.ohlcv import OHLCV; import asyncio
asyncio.run(OHLCV().get_historical_ohlcv("INDEX:NDFI", "1D", 30))
```

**CLI Testing:**

```bash
python -m tvkit price NASDAQ:AAPL        # Get Apple's price
python -m tvkit crypto 3                 # Top 3 crypto prices
python -m tvkit compare NASDAQ:AAPL NASDAQ:GOOGL  # Compare stocks
python -m tvkit help                     # Show help
```

**Verify Installation:**

```bash
# Run verification script
uv run python examples/verify_installation.py
# Or: python examples/verify_installation.py
```

### Installation

**Method 1: Using uv (Recommended)**
```bash
# Install tvkit using uv
uv add tvkit

# Or create a new project with tvkit
uv init my-trading-project
cd my-trading-project
uv add tvkit
```

**Method 2: Using pip from source**
```bash
# Clone the repository
git clone https://github.com/lumduan/tvkit.git
cd tvkit

# Install with pip
pip install .

# For development installation
pip install -e '.[dev]'
```

**Method 3: Direct pip installation**
```bash
# Install from PyPI
pip install tvkit

# Install with all optional dependencies
pip install 'tvkit[dev]'
```

### Basic Real-time Data Streaming

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def stream_bitcoin():
    async with OHLCV() as client:
        # Stream real-time OHLCV data for Bitcoin
        count = 0
        async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="1"):
            count += 1
            print(f"Bar {count}: BTC ${bar.close:,.2f} | Volume: {bar.volume:,.0f}")
            
            # Limit demo to 5 bars
            if count >= 5:
                break

asyncio.run(stream_bitcoin())
```

**Sample Output:**
```
Bar 1: BTC $43,250.50 | Volume: 125,430
Bar 2: BTC $43,275.25 | Volume: 98,750
Bar 3: BTC $43,290.75 | Volume: 156,890
Bar 4: BTC $43,245.00 | Volume: 134,200
Bar 5: BTC $43,267.50 | Volume: 145,600
```

### Historical Data & Export

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter
from tvkit.api.utils import convert_timestamp_to_iso

async def fetch_and_export_apple_data():
    # Fetch historical Apple stock data
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(
            "NASDAQ:AAPL",
            interval="1D",  # Daily bars
            bars_count=30   # Last 30 days
        )
    
    print(f"📊 Fetched {len(bars)} daily bars for Apple")
    print(f"📅 Date range: {convert_timestamp_to_iso(bars[0].timestamp)[:10]} to {convert_timestamp_to_iso(bars[-1].timestamp)[:10]}")
    
    # Show first 3 bars
    print("\n🔍 First 3 bars:")
    for i, bar in enumerate(bars[:3]):
        date = convert_timestamp_to_iso(bar.timestamp)[:10]
        print(f"  {date}: Open=${bar.open:.2f}, High=${bar.high:.2f}, Low=${bar.low:.2f}, Close=${bar.close:.2f}, Volume={bar.volume:,.0f}")
    
    # Export to multiple formats
    exporter = DataExporter()
    
    # Export to Polars DataFrame with technical analysis
    df = await exporter.to_polars(bars, add_analysis=True)
    print(f"\n📈 DataFrame created: {df.shape[0]} rows × {df.shape[1]} columns")
    print(f"Columns: {', '.join(df.columns[:8])}...")
    
    # Export to files
    json_path = await exporter.to_json(bars, "./export/apple_data.json", include_metadata=True)
    csv_path = await exporter.to_csv(bars, "./export/apple_data.csv", include_metadata=True)
    
    print(f"\n💾 Exported to:")
    print(f"   JSON: {json_path}")
    print(f"   CSV: {csv_path}")
    
    return df

asyncio.run(fetch_and_export_apple_data())
```

**Sample Output:**
```
📊 Fetched 30 daily bars for Apple
📅 Date range: 2024-06-15 to 2024-07-15

🔍 First 3 bars:
  2024-06-15: Open=$189.25, High=$191.50, Low=$188.75, Close=$190.90, Volume=52,430,200
  2024-06-16: Open=$190.85, High=$192.30, Low=$189.40, Close=$191.75, Volume=48,750,150
  2024-06-17: Open=$191.80, High=$193.20, Low=$190.95, Close=$192.45, Volume=55,890,300

📈 DataFrame created: 30 rows × 12 columns
Columns: timestamp, open, high, low, close, volume, sma_20, sma_50...

💾 Exported to:
   JSON: ./export/apple_data.json
   CSV: ./export/apple_data.csv
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

### Multi-Market Stock Scanner

```python
import asyncio
from tvkit.api.scanner import ScannerService, Market, MarketRegion
from tvkit.api.scanner import create_comprehensive_request, ColumnSets, get_markets_by_region

async def scan_asian_markets():
    service = ScannerService()
    
    # Create comprehensive request for top stocks by market cap
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=5  # Top 5 stocks per market
    )
    
    # Scan specific Asian markets
    markets_to_scan = [Market.THAILAND, Market.JAPAN, Market.SINGAPORE]
    
    print("🌏 Scanning Asian Markets for Top Stocks by Market Cap")
    print("=" * 60)
    
    for market in markets_to_scan:
        print(f"\n📊 Scanning {market.value.title()} market...")
        
        response = await service.scan_market(market, request)
        print(f"✅ Found {len(response.data)} stocks")
        
        if response.data:
            top_stock = response.data[0]  # Market leader
            print(f"\n🏆 Market Leader:")
            print(f"   Symbol: {top_stock.name}")
            print(f"   Price: {top_stock.close} {top_stock.currency}")
            if top_stock.market_cap_basic:
                print(f"   Market Cap: ${top_stock.market_cap_basic:,.0f}")
            if top_stock.price_earnings_ttm:
                print(f"   P/E Ratio: {top_stock.price_earnings_ttm:.2f}")
            print(f"   Sector: {top_stock.sector or 'N/A'}")
    
    # Regional analysis
    print(f"\n🌍 Regional Analysis - Asia Pacific Markets:")
    asia_markets = get_markets_by_region(MarketRegion.ASIA_PACIFIC)
    print(f"Total Asia Pacific markets available: {len(asia_markets)}")
    
    return response.data

asyncio.run(scan_asian_markets())
```

**Sample Output:**
```
🌏 Scanning Asian Markets for Top Stocks by Market Cap
============================================================

📊 Scanning Thailand market...
✅ Found 5 stocks

🏆 Market Leader:
   Symbol: PTT
   Price: 38.50 THB
   Market Cap: $25,340,000,000
   P/E Ratio: 12.45
   Sector: Energy

📊 Scanning Japan market...
✅ Found 5 stocks

🏆 Market Leader:
   Symbol: 7203
   Price: 2,845.50 JPY
   Market Cap: $185,200,000,000
   P/E Ratio: 8.92
   Sector: Consumer Cyclical

📊 Scanning Singapore market...
✅ Found 5 stocks

🏆 Market Leader:
   Symbol: D05
   Price: 31.82 SGD
   Market Cap: $95,750,000,000
   P/E Ratio: 13.21
   Sector: Financial Services

🌍 Regional Analysis - Asia Pacific Markets:
Total Asia Pacific markets available: 17
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
- **Macro Indicators**: INDEX:NDFI (Net Demand For Income), USI:PCC (Put/Call Ratio)
- **Quantitative Analysis**: Liquidity regime detection, market breadth analysis

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
        "OANDA:XAUUSD",       # Commodities (Gold)
        "INDEX:NDFI",         # Macro Liquidity Indicator
        "USI:PCC"             # Put/Call Ratio
    ]

    async with OHLCV() as client:
        async for trade_info in client.get_latest_trade_info(symbols):
            # Process multi-asset trade information
            print(f"Portfolio update: {trade_info}")
```

### Macro Liquidity and Market Breadth Indicators

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def analyze_macro_liquidity():
    """Access macro indicators for quantitative analysis."""

    # Key indicators for systematic trading strategies
    macro_indicators = {
        "INDEX:NDFI": "Net Demand For Income (Market Breadth)",
        "USI:PCC": "Put/Call Ratio (Sentiment & Liquidity)"
    }

    async with OHLCV() as client:
        for symbol, description in macro_indicators.items():
            print(f"📊 Fetching {symbol} - {description}")

            # Get historical data for analysis
            data = await client.get_historical_ohlcv(
                exchange_symbol=symbol,
                interval="1D",
                bars_count=100  # ~3-4 months
            )

            # Calculate percentile for regime detection
            values = [bar.close for bar in data]
            current = data[-1].close
            percentile = sum(1 for v in values if v <= current) / len(values) * 100

            print(f"   Current Level: {current:.6f} ({percentile:.1f}th percentile)")

            # Simple regime classification
            if symbol == "INDEX:NDFI":
                regime = "High Liquidity" if percentile > 75 else "Low Liquidity" if percentile < 25 else "Neutral"
                print(f"   Liquidity Regime: {regime}")
            elif symbol == "USI:PCC":
                sentiment = "Extreme Fear" if percentile > 80 else "Complacency" if percentile < 20 else "Neutral"
                print(f"   Market Sentiment: {sentiment}")

# Run the analysis
asyncio.run(analyze_macro_liquidity())
```

## 📦 Dependencies

**tvkit** uses modern, high-performance libraries:

- **[Polars](https://pola.rs/)** (≥1.0.0): Fast DataFrame operations
- **[Pydantic](https://pydantic.dev/)** (≥2.11.7): Data validation and settings
- **[websockets](https://websockets.readthedocs.io/)** (≥13.0): Async WebSocket client
- **[httpx](https://www.python-httpx.org/)** (≥0.28.0): Async HTTP client
- **Python 3.11+**: Modern async/await support

## 📚 Complete Getting Started Guide

### 1. Quick Installation & First Run

**Install and test tvkit in under 2 minutes:**

```bash
# Method 1: Using uv (fastest)
uv init my-trading-app && cd my-trading-app
uv add tvkit
uv run python -c "import tvkit; print('✅ tvkit installed successfully!')"

# Method 2: Using pip
pip install tvkit
python -c "import tvkit; print('✅ tvkit installed successfully!')"
```

### 2. Your First Trading Data Script

Create `first_script.py` and run it:

```python
#!/usr/bin/env python3
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def my_first_trading_data():
    async with OHLCV() as client:
        # Get Apple's latest price
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", 1)
        latest = bars[0]
        print(f"🍎 Apple (AAPL): ${latest.close:.2f}")
        
        # Get Bitcoin's latest price  
        bars = await client.get_historical_ohlcv("BINANCE:BTCUSDT", "1D", 1)
        latest = bars[0]
        print(f"💰 Bitcoin: ${latest.close:,.2f}")

if __name__ == "__main__":
    asyncio.run(my_first_trading_data())
```

**Run it:**
```bash
# With uv
uv run python first_script.py

# With pip
python first_script.py
```

**Expected output:**
```
🍎 Apple (AAPL): $192.75
💰 Bitcoin: $43,267.50
```

### 3. Development Environment Setup

**For Contributors:**

```bash
# Clone and setup development environment
git clone https://github.com/lumduan/tvkit.git
cd tvkit

# Using uv (recommended)
uv sync
uv run ruff check . && uv run ruff format . && uv run mypy tvkit/
uv run python -m pytest tests/ -v --cov=tvkit

# Using pip
pip install -r requirements.txt
pip install mypy ruff pytest pytest-asyncio pytest-cov
ruff check . && ruff format . && mypy tvkit/
python -m pytest tests/ -v --cov=tvkit
```

### 4. Explore Comprehensive Examples

```bash
# Comprehensive historical and real-time data demo
uv run python examples/historical_and_realtime_data.py
# ⏱️ Runtime: ~2-3 minutes | 📋 Features: OHLCV, exports, multi-symbol, streaming, macro indicators

# Global market scanner with 69 markets
uv run python examples/multi_market_scanner_example.py
# ⏱️ Runtime: ~1-2 minutes | 📋 Features: Regional analysis, 101+ metrics

# Quick tutorial with macro indicators
uv run python examples/quick_tutorial.py
# ⏱️ Runtime: ~1 minute | 📋 Features: Basic usage, macro indicators (INDEX:NDFI, USI:PCC)

# Multiple export formats demo
uv run python examples/export_demo.py
# ⏱️ Runtime: ~30 seconds | 📋 Features: Polars, JSON, CSV, Parquet
```

## 📖 Documentation

- **[Real-time Streaming Guide](docs/realtime_streaming.md)**: WebSocket streaming documentation
- **[Polars Integration](docs/POLARS_INTEGRATION.md)**: Data processing and analysis
- **[OHLCV Client Documentation](docs/api/chart/ohlcv.md)**: Primary client for real-time OHLCV data streaming and historical data retrieval
- **[Chart Utils Documentation](docs/api/chart/utils.md)**: Utility functions for interval validation and chart API operations
- **[ScannerService Documentation](docs/api/scanner/services/scanner_service.md)**: Market screening service for 69+ global markets with 101+ financial metrics
- **[Markets Documentation](docs/api/scanner/markets.md)**: Global market identifiers, exchange information, and regional organization for 69+ markets
- **[ConnectionService Documentation](docs/api/chart/services/connection_service.md)**: WebSocket connection management and TradingView session handling
- **[MessageService Documentation](docs/api/chart/services/message_service.md)**: WebSocket message construction, protocol handling, and transmission
- **[Utils Documentation](docs/api/utils.md)**: Utility functions for timestamp conversion, symbol format conversion, flexible symbol validation, and TradingView indicators
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

## 🚀 Performance & Scale

**tvkit** is designed for production use:

- **Concurrent Operations**: Full async support for high-throughput applications
- **Global Market Coverage**: 69 markets, 6 regions, 101+ financial metrics
- **Real-time Streaming**: WebSocket connections with automatic reconnection
- **Type Safety**: Complete Pydantic validation prevents runtime errors
- **Export Performance**: Polars-powered data processing for large datasets
- **Error Resilience**: Comprehensive retry logic and graceful degradation

### Benchmarks (Approximate)

| Operation | Performance | Notes |
|-----------|-------------|-------|
| Historical Data Fetch | ~100-500ms | Per symbol, 100 bars |
| Market Scanner Query | ~200-800ms | Per market, 50 stocks |
| Real-time Streaming | <50ms latency | Per update |
| Polars DataFrame Export | ~10-50ms | 1000 bars with analysis |
| JSON/CSV Export | ~20-100ms | 1000 bars with metadata |

---

**Ready to get started?** 🚀 Choose your installation method above and run your first script!

Built with ❤️ for the financial data community
