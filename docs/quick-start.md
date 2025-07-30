# 🚀 Quick Start Guide

Get started with **tvkit** in just a few minutes! This guide will walk you through installation, basic usage, and your first data streaming example.

## 📦 Installation

### Using uv (Recommended)
```bash
# Install tvkit with uv
uv add tvkit

# Or create a new project with tvkit
uv init my-trading-project
cd my-trading-project
uv add tvkit
```

### Using pip
```bash
# Install from PyPI
pip install tvkit

# For development dependencies
pip install "tvkit[dev]"
```

### Requirements
- **Python 3.13+** - Modern async/await support required
- **Internet connection** - For real-time data streaming
- **Optional**: Jupyter Notebook for interactive analysis

## 🎯 5-Minute Tutorial

### 1. Your First Data Stream

Create a file called `my_first_stream.py`:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def main():
    # Connect to TradingView's data stream
    async with OHLCV() as client:
        print("🚀 Starting Bitcoin price stream...")
        
        # Stream real-time OHLCV data for Bitcoin
        async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="1"):
            print(f"🪙 BTC: ${bar.close:,.2f} | Volume: {bar.volume:,.0f}")
            
            # Stop after 10 bars for demo
            if bar.time_close:
                break

# Run the stream
asyncio.run(main())
```

Run it:
```bash
uv run python my_first_stream.py
# or
python my_first_stream.py
```

### 2. Historical Data & Export

Create `historical_analysis.py`:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def analyze_historical_data():
    # Fetch historical Bitcoin data
    async with OHLCV() as client:
        print("📈 Fetching historical Bitcoin data...")
        
        bars = await client.get_historical_ohlcv(
            "BINANCE:BTCUSDT",
            interval="60",        # 1-hour bars
            bars_count=100        # Last 100 hours
        )
    
    print(f"✅ Got {len(bars)} historical bars")
    
    # Export to different formats
    exporter = DataExporter()
    
    # 1. Export to Polars DataFrame with technical analysis
    df = await exporter.to_polars(bars, add_analysis=True)
    print(f"📊 DataFrame: {len(df)} rows × {len(df.columns)} columns")
    print("Columns:", list(df.columns))
    
    # 2. Export to JSON file
    json_result = await exporter.to_json(bars, "btc_historical.json")
    print(f"💾 Exported to: {json_result.file_path}")
    
    # 3. Export to CSV file
    csv_result = await exporter.to_csv(bars, "btc_historical.csv")
    print(f"📄 Exported to: {csv_result.file_path}")
    
    # Show sample data
    print("\n📈 Sample data:")
    print(df.head(3))

# Run the analysis
asyncio.run(analyze_historical_data())
```

### 3. Multi-Symbol Monitoring

Create `portfolio_monitor.py`:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV

async def monitor_portfolio():
    # Define your portfolio symbols
    symbols = [
        "BINANCE:BTCUSDT",    # Bitcoin
        "NASDAQ:AAPL",        # Apple Stock
        "FOREX:EURUSD",       # Euro/USD
        "BINANCE:ETHUSDT"     # Ethereum
    ]
    
    async with OHLCV() as client:
        print("🎯 Monitoring portfolio...")
        
        # Get latest trade information for all symbols
        async for trade_info in client.get_latest_trade_info(symbols):
            symbol = trade_info.symbol
            price = trade_info.price
            change = trade_info.change_percent
            
            # Format change with color indicators
            change_emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
            
            print(f"{change_emoji} {symbol}: ${price:,.4f} ({change:+.2f}%)")

# Run the monitor
asyncio.run(monitor_portfolio())
```

## 🔧 Configuration & Advanced Usage

### Custom Export Configuration

```python
from tvkit.export import DataExporter, ExportConfig, ExportFormat

# Configure custom export settings
config = ExportConfig(
    format=ExportFormat.CSV,
    timestamp_format="iso",      # ISO 8601 timestamps
    include_metadata=True,       # Include metadata file
    options={
        "delimiter": ";",        # Use semicolon delimiter
        "include_headers": True, # Include column headers
        "float_precision": 4     # 4 decimal places
    }
)

# Export with custom configuration
exporter = DataExporter()
result = await exporter.export_ohlcv_data(
    bars, 
    ExportFormat.CSV, 
    config=config
)
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
                    print(f"💰 Price: ${bar.close}")
                    
        except Exception as e:
            retry_count += 1
            wait_time = 2 ** retry_count  # Exponential backoff
            print(f"❌ Error: {e}")
            print(f"🔄 Retrying in {wait_time}s... ({retry_count}/{max_retries})")
            await asyncio.sleep(wait_time)
        else:
            print("✅ Stream completed successfully!")
            break
    
    if retry_count >= max_retries:
        print("❌ Max retries exceeded. Stream failed.")

asyncio.run(robust_streaming())
```

## 📊 Data Types & Intervals

### Supported Intervals
- **Intraday**: `1`, `3`, `5`, `15`, `30` (minutes)
- **Hourly**: `60`, `120`, `240` (minutes)  
- **Daily**: `1D`
- **Weekly**: `1W`
- **Monthly**: `1M`

### Symbol Format Examples
```python
# Cryptocurrencies
"BINANCE:BTCUSDT"     # Bitcoin/USDT on Binance
"COINBASE:BTCUSD"     # Bitcoin/USD on Coinbase

# Stocks
"NASDAQ:AAPL"         # Apple on NASDAQ
"NYSE:MSFT"           # Microsoft on NYSE
"TSE:SHOP"            # Shopify on Toronto Stock Exchange

# Forex
"FOREX:EURUSD"        # Euro/USD
"FOREX:GBPJPY"        # British Pound/Japanese Yen

# Commodities
"OANDA:XAUUSD"        # Gold/USD
"NYMEX:CL1!"          # Crude Oil Futures
```

## 🧪 Testing Your Setup

Create `test_setup.py` to verify everything works:

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter

async def test_setup():
    """Test tvkit installation and basic functionality"""
    
    print("🧪 Testing tvkit setup...")
    
    try:
        # Test 1: Connection
        async with OHLCV() as client:
            print("✅ Connection test passed")
            
            # Test 2: Historical data
            bars = await client.get_historical_ohlcv(
                "BINANCE:BTCUSDT", 
                interval="60", 
                bars_count=5
            )
            print(f"✅ Historical data test passed ({len(bars)} bars)")
            
            # Test 3: Export functionality
            exporter = DataExporter()
            df = await exporter.to_polars(bars)
            print(f"✅ Export test passed ({len(df)} rows)")
            
        print("🎉 All tests passed! tvkit is ready to use.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("💡 Check your internet connection and try again.")

# Run the test
asyncio.run(test_setup())
```

## 🎯 Next Steps

Now that you have tvkit working, explore these advanced features:

1. **[Real-time Streaming](realtime_streaming.md)** - Advanced WebSocket streaming patterns
2. **[Data Export System](export_system.md)** - Multi-format export capabilities
3. **[Polars Integration](POLARS_INTEGRATION.md)** - High-performance data processing
4. **[API Reference](api/)** - Complete API documentation

## 🆘 Troubleshooting

### Common Issues

**ImportError: No module named 'tvkit'**
```bash
# Make sure tvkit is installed
uv add tvkit
# or
pip install tvkit
```

**Connection timeout errors**
```python
# Add timeout configuration
async with OHLCV(timeout=30) as client:  # 30-second timeout
    # your code here
```

**Symbol not found errors**
```python
# Verify symbol format is correct
# Use TradingView's symbol search: https://www.tradingview.com/
symbol = "BINANCE:BTCUSDT"  # Correct format
```

### Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/lumduan/tvkit/issues)
- **Documentation**: Check the [full documentation](README.md)
- **Examples**: Browse the [examples directory](../examples/)

## 🎉 You're Ready!

Congratulations! You now have tvkit set up and ready for financial data analysis. Start building your trading applications and data pipelines with confidence!