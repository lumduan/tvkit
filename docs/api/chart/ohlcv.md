# OHLCV Client Documentation

## Overview

The `OHLCV` class is the primary high-level client for streaming real-time financial market data from TradingView. It provides a user-friendly async interface for accessing OHLCV (Open, High, Low, Close, Volume) bars, quote data, and trade information across multiple asset classes including stocks, cryptocurrencies, forex, and commodities.

**Module Path**: `tvkit.api.chart.ohlcv`

## Architecture

The OHLCV client serves as the main entry point for tvkit's real-time data streaming capabilities:

- **High-Level Interface**: Abstracts complex WebSocket protocol details behind simple async methods
- **Multi-Asset Support**: Handles stocks, crypto, forex, commodities with unified API
- **Async Context Manager**: Provides safe resource management with automatic cleanup
- **Multiple Data Types**: Supports structured OHLCV bars, quote data, and raw message streams
- **Error Handling**: Comprehensive validation and error recovery patterns
- **Type Safety**: Full Pydantic model integration for type-safe data structures

## Class Definition

### OHLCV

```python
class OHLCV:
    """
    A real-time data streaming client for TradingView WebSocket API.

    This class provides async generators for streaming live market data including
    OHLCV bars, quote data, and trade information from TradingView.
    """
```

#### Constructor

```python
def __init__(self) -> None
```

**Description**: Initializes the OHLCV client with default WebSocket connection parameters for TradingView data streaming.

**Default Configuration**:
- **WebSocket URL**: `wss://data.tradingview.com/socket.io/websocket?from=screener%2F`
- **Connection Service**: Initialized on first use
- **Message Service**: Initialized on first use
- **Logging Level**: WARNING (configurable)

**Attributes**:
- `ws_url` (str): WebSocket URL for TradingView connection
- `connection_service` (Optional[ConnectionService]): WebSocket connection management
- `message_service` (Optional[MessageService]): Message protocol handling

### Context Manager Support

#### __aenter__() and __aexit__()

```python
async def __aenter__(self) -> "OHLCV"
async def __aexit__(self, exc_type, exc_val, exc_tb) -> None
```

**Description**: Provides async context manager support for automatic resource management.

**Resource Management**:
- **Entry**: Returns the OHLCV instance ready for use
- **Exit**: Automatically closes WebSocket connections and cleans up resources
- **Exception Safety**: Ensures cleanup even when exceptions occur

**Usage Pattern**:
```python
async with OHLCV() as client:
    # Use client methods here
    async for bar in client.get_ohlcv("NASDAQ:AAPL"):
        print(f"Price: ${bar.close}")
# Automatic cleanup happens here
```

## Core Methods

### Real-Time OHLCV Streaming

#### get_ohlcv()

```python
async def get_ohlcv(
    self,
    exchange_symbol: str,
    interval: str = "1",
    bars_count: int = 10
) -> AsyncGenerator[OHLCVBar, None]
```

**Description**: Returns an async generator that yields structured OHLCV data for a specified symbol in real-time.

**Parameters**:
- `exchange_symbol` (str): Symbol in 'EXCHANGE:SYMBOL' format (e.g., 'BINANCE:BTCUSDT')
- `interval` (str): Time interval for bars (default: "1" for 1 minute)
- `bars_count` (int): Number of historical bars to fetch initially (default: 10)

**Returns**: AsyncGenerator yielding `OHLCVBar` objects with:
- `timestamp` (int): Unix timestamp in seconds
- `open` (float): Opening price
- `high` (float): Highest price in interval
- `low` (float): Lowest price in interval
- `close` (float): Closing price
- `volume` (int): Trading volume

**Supported Intervals**:
- **Minutes**: "1", "5", "15", "30"
- **Hours**: "60", "120", "240"
- **Days**: "1D"
- **Weeks**: "1W"
- **Months**: "1M"

**Supported Exchanges**:
- **Crypto**: BINANCE, COINBASE, KRAKEN, BITFINEX
- **Stocks**: NASDAQ, NYSE, LSE, TSE
- **Forex**: FOREX, OANDA, FX_IDC
- **Commodities**: COMEX, NYMEX

**Message Processing**:
- **Real-time Updates** (`du`): Live price updates as new bars form
- **Historical Data** (`timescale_update`): Initial historical bars
- **Quote Data** (`qsd`): Current price information
- **Status Messages** (`quote_completed`): Setup confirmation

**Error Handling**:
- `ValueError`: Invalid symbol format or interval
- `WebSocketException`: Connection or streaming errors
- `RuntimeError`: Service initialization failures

**Usage Example**:
```python
async with OHLCV() as client:
    count = 0
    async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="5", bars_count=50):
        count += 1
        print(f"Bar {count}: BTC ${bar.close:,.2f} | Volume: {bar.volume:,.0f}")
        print(f"Time: {convert_timestamp_to_iso(bar.timestamp)}")

        # Limit to 10 bars for demo
        if count >= 10:
            break
```

### Historical Data Retrieval

#### get_historical_ohlcv()

```python
async def get_historical_ohlcv(
    self,
    exchange_symbol: str,
    interval: str = "1",
    bars_count: int = 10
) -> list[OHLCVBar]
```

**Description**: Fetches a complete list of historical OHLCV data for analysis and backtesting.

**Parameters**:
- `exchange_symbol` (str): Symbol in 'EXCHANGE:SYMBOL' format
- `interval` (str): Time interval (default: "1")
- `bars_count` (int): Number of historical bars to fetch (default: 10)

**Returns**: List of `OHLCVBar` objects sorted chronologically (oldest first)

**Implementation Details**:
- **Timeout Protection**: 30-second timeout to prevent indefinite waiting
- **Data Aggregation**: Collects bars from multiple message types
- **Sorting**: Results sorted by timestamp for chronological analysis
- **Validation**: Ensures at least one bar is received before returning

**Error Handling**:
- `RuntimeError`: No historical data received within timeout period
- `ValueError`: Invalid symbol format or interval
- `WebSocketException`: Connection failures

**Usage Example**:
```python
async with OHLCV() as client:
    # Fetch 30 days of Apple stock data
    bars = await client.get_historical_ohlcv(
        "NASDAQ:AAPL",
        interval="1D",
        bars_count=30
    )

    print(f"Fetched {len(bars)} daily bars")
    print(f"Date range: {convert_timestamp_to_iso(bars[0].timestamp)[:10]} to {convert_timestamp_to_iso(bars[-1].timestamp)[:10]}")

    # Calculate price change
    price_change = ((bars[-1].close - bars[0].close) / bars[0].close) * 100
    print(f"30-day price change: {price_change:.2f}%")
```

### Quote Data Streaming

#### get_quote_data()

```python
async def get_quote_data(
    self,
    exchange_symbol: str,
    interval: str = "1",
    bars_count: int = 10
) -> AsyncGenerator[QuoteSymbolData, None]
```

**Description**: Streams real-time quote data including current price, volume, and market information.

**Parameters**:
- `exchange_symbol` (str): Symbol in 'EXCHANGE:SYMBOL' format
- `interval` (str): Time interval (default: "1")
- `bars_count` (int): Historical bar count for context (default: 10)

**Returns**: AsyncGenerator yielding `QuoteSymbolData` objects with:
- `current_price` (Optional[float]): Current market price
- `symbol_info` (dict): Symbol metadata and market information
- `volume` (Optional[int]): Current trading volume
- `change` (Optional[float]): Price change from previous close
- `change_percent` (Optional[float]): Percentage change

**Use Cases**:
- **Real-time Price Monitoring**: Track current prices without full OHLCV data
- **Market Scanning**: Monitor multiple symbols for price alerts
- **Quote-Only Assets**: Assets that provide quotes but not full chart data
- **High-Frequency Updates**: More frequent updates than OHLCV bars

**Usage Example**:
```python
async with OHLCV() as client:
    async for quote in client.get_quote_data("NASDAQ:AAPL", interval="1"):
        if quote.current_price:
            change_pct = quote.change_percent or 0
            direction = "📈" if change_pct >= 0 else "📉"
            print(f"{direction} AAPL: ${quote.current_price:.2f} ({change_pct:+.2f}%)")
```

### Raw Data Access

#### get_ohlcv_raw()

```python
async def get_ohlcv_raw(
    self,
    exchange_symbol: str,
    interval: str = "1",
    bars_count: int = 10
) -> AsyncGenerator[dict[str, Any], None]
```

**Description**: Provides access to raw JSON messages from TradingView for debugging and custom parsing.

**Parameters**:
- `exchange_symbol` (str): Symbol in 'EXCHANGE:SYMBOL' format
- `interval` (str): Time interval (default: "1")
- `bars_count` (int): Historical bar count (default: 10)

**Returns**: AsyncGenerator yielding raw JSON dictionary objects

**Use Cases**:
- **Protocol Debugging**: Inspect raw WebSocket messages
- **Custom Parsing**: Implement specialized data extraction
- **Format Analysis**: Understand TradingView message structures
- **Integration Development**: Build custom message handlers

**Message Types Yielded**:
- **Data Updates** (`du`): Real-time OHLCV updates
- **Timescale Updates** (`timescale_update`): Historical data batches
- **Quote Symbol Data** (`qsd`): Price and volume updates
- **Status Messages**: Connection and session status
- **Heartbeats**: Connection keep-alive messages

**Usage Example**:
```python
async with OHLCV() as client:
    message_count = 0
    async for raw_data in client.get_ohlcv_raw("BINANCE:BTCUSDT", interval="1"):
        message_count += 1
        print(f"Message {message_count}: {raw_data.get('m', 'Unknown type')}")

        # Print full message for debugging
        if message_count <= 5:
            print(f"  Full data: {raw_data}")

        if message_count >= 20:
            break
```

### Multi-Symbol Monitoring

#### get_latest_trade_info()

```python
async def get_latest_trade_info(
    self,
    exchange_symbol: List[str]
) -> AsyncGenerator[dict[str, Any], None]
```

**Description**: Monitors multiple symbols simultaneously for comprehensive portfolio tracking.

**Parameters**:
- `exchange_symbol` (List[str]): List of symbols in 'EXCHANGE:SYMBOL' format

**Returns**: AsyncGenerator yielding trade information dictionaries with:
- **Symbol Data**: Current prices, changes, volumes
- **Market Information**: Exchange details, trading status
- **Timestamp Data**: Last trade times and updates
- **Metadata**: Symbol descriptions and currency information

**Use Cases**:
- **Portfolio Monitoring**: Track multiple investments simultaneously
- **Market Scanning**: Monitor sector or theme-based symbol groups
- **Arbitrage Detection**: Compare prices across different exchanges
- **Risk Management**: Real-time monitoring of position values

**Supported Symbol Types**:
- **Mixed Assets**: Combine stocks, crypto, forex, commodities
- **Cross-Exchange**: Monitor same asset on different exchanges
- **Currency Pairs**: Multiple forex pairs simultaneously
- **Sector Groups**: Industry-specific symbol collections

**Usage Example**:
```python
# Define a diverse portfolio
portfolio_symbols = [
    "NASDAQ:AAPL",      # Apple stock
    "NASDAQ:GOOGL",     # Google stock
    "BINANCE:BTCUSDT",  # Bitcoin
    "BINANCE:ETHUSDT",  # Ethereum
    "FOREX:EURUSD",     # EUR/USD forex
    "OANDA:XAUUSD"      # Gold futures
]

async with OHLCV() as client:
    async for trade_info in client.get_latest_trade_info(portfolio_symbols):
        # Process multi-symbol updates
        message_type = trade_info.get('m')
        if message_type == 'qsd':  # Quote symbol data
            symbol_data = trade_info.get('p', [{}])[1]
            symbol = symbol_data.get('n', 'Unknown')
            price = symbol_data.get('lp', 'N/A')
            change = symbol_data.get('ch', 0)

            print(f"{symbol}: ${price} ({change:+.2f})")
```

## Internal Methods

### Service Management

#### _setup_services()

```python
async def _setup_services(self) -> None
```

**Description**: Initializes and connects the underlying WebSocket services.

**Process Flow**:
1. **ConnectionService Creation**: Initializes WebSocket connection management
2. **Connection Establishment**: Connects to TradingView WebSocket endpoint
3. **MessageService Creation**: Sets up message protocol handler
4. **Service Linking**: Links message service to active WebSocket connection

**Error Handling**:
- Ensures services are only initialized once per client instance
- Propagates connection errors to calling methods
- Provides consistent service state across all client methods

## Data Models Integration

The OHLCV client integrates with several Pydantic models for type-safe data handling:

### Core Data Models

**OHLCVBar**: Structured OHLCV data
```python
class OHLCVBar(BaseModel):
    timestamp: int          # Unix timestamp (seconds)
    open: float            # Opening price
    high: float            # Highest price
    low: float             # Lowest price
    close: float           # Closing price
    volume: int            # Trading volume
```

**QuoteSymbolData**: Real-time quote information
```python
class QuoteSymbolData(BaseModel):
    current_price: Optional[float]     # Current market price
    symbol_info: dict                  # Symbol metadata
    volume: Optional[int]              # Trading volume
    change: Optional[float]            # Price change
    change_percent: Optional[float]    # Percentage change
```

**WebSocketMessage**: Generic message wrapper
```python
class WebSocketMessage(BaseModel):
    message_type: str      # Message type identifier ('du', 'qsd', etc.)
    data: dict            # Message payload
```

### Response Models

**OHLCVResponse**: Structured OHLCV message parsing
**TimescaleUpdateResponse**: Historical data batch processing
**QuoteCompletedMessage**: Session setup confirmation

## Symbol Format Reference

### Exchange:Symbol Format

All methods require symbols in the standardized format: `EXCHANGE:SYMBOL`

**Stock Examples**:
```python
"NASDAQ:AAPL"     # Apple Inc.
"NYSE:MSFT"       # Microsoft Corp.
"LSE:VODL"        # Vodafone Group PLC
"TSE:7203"        # Toyota Motor Corp.
```

**Cryptocurrency Examples**:
```python
"BINANCE:BTCUSDT"     # Bitcoin/USDT on Binance
"COINBASE:ETHUSD"     # Ethereum/USD on Coinbase
"KRAKEN:XRPEUR"       # XRP/EUR on Kraken
"BITFINEX:LTCBTC"     # Litecoin/Bitcoin on Bitfinex
```

**Forex Examples**:
```python
"FOREX:EURUSD"        # Euro/US Dollar
"OANDA:GBPJPY"        # British Pound/Japanese Yen
"FX_IDC:USDCAD"       # US Dollar/Canadian Dollar
"FOREX:AUDUSD"        # Australian Dollar/US Dollar
```

**Commodities Examples**:
```python
"COMEX:GC1!"          # Gold futures
"NYMEX:CL1!"          # Crude oil futures
"COMEX:SI1!"          # Silver futures
"NYMEX:NG1!"          # Natural gas futures
```

### Symbol Validation

The client automatically validates symbol formats using the `validate_symbols()` utility:

- **Format Check**: Ensures "EXCHANGE:SYMBOL" pattern
- **Exchange Validation**: Verifies exchange is supported
- **Symbol Verification**: Confirms symbol exists on specified exchange

## Error Handling Patterns

### Connection Management

```python
async def handle_connection_errors():
    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            async with OHLCV() as client:
                async for bar in client.get_ohlcv("NASDAQ:AAPL"):
                    print(f"AAPL: ${bar.close}")
                    break
            break  # Success, exit retry loop

        except WebSocketException as e:
            logging.error(f"WebSocket error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                raise

        except ValueError as e:
            logging.error(f"Invalid symbol format: {e}")
            break  # Don't retry validation errors
```

### Data Validation

```python
async def robust_data_processing():
    async with OHLCV() as client:
        async for bar in client.get_ohlcv("BINANCE:BTCUSDT"):
            # Validate data completeness
            if all([bar.open, bar.high, bar.low, bar.close, bar.volume]):
                # Validate data consistency
                if bar.low <= bar.open <= bar.high and bar.low <= bar.close <= bar.high:
                    print(f"Valid bar: ${bar.close}")
                else:
                    logging.warning(f"Inconsistent OHLC data: {bar}")
            else:
                logging.warning(f"Incomplete bar data: {bar}")
```

### Timeout Handling

```python
async def fetch_with_timeout():
    async with OHLCV() as client:
        try:
            # Set overall timeout for the operation
            bars = await asyncio.wait_for(
                client.get_historical_ohlcv("NASDAQ:AAPL", "1D", 30),
                timeout=60.0  # 60-second timeout
            )
            print(f"Fetched {len(bars)} bars successfully")

        except asyncio.TimeoutError:
            logging.error("Historical data fetch timed out")
        except RuntimeError as e:
            logging.error(f"No data received: {e}")
```

## Performance Optimization

### Efficient Symbol Monitoring

```python
async def optimized_multi_symbol_monitoring():
    symbols = ["NASDAQ:AAPL", "NASDAQ:GOOGL", "NASDAQ:MSFT"]

    async with OHLCV() as client:
        # Use multi-symbol method for efficiency
        async for trade_info in client.get_latest_trade_info(symbols):
            # Process all symbols in single stream
            if trade_info.get('m') == 'qsd':
                symbol_data = trade_info.get('p', [{}])[1]
                symbol = symbol_data.get('n')
                price = symbol_data.get('lp')
                if symbol and price:
                    print(f"{symbol}: ${price}")
```

### Memory-Efficient Historical Data

```python
async def process_large_historical_dataset():
    async with OHLCV() as client:
        # Fetch data in chunks to manage memory
        chunk_size = 100
        total_bars_needed = 1000
        all_bars = []

        for i in range(0, total_bars_needed, chunk_size):
            bars = await client.get_historical_ohlcv(
                "NASDAQ:AAPL",
                "1D",
                min(chunk_size, total_bars_needed - i)
            )

            # Process immediately to reduce memory usage
            processed_data = [
                {"date": convert_timestamp_to_iso(bar.timestamp)[:10], "close": bar.close}
                for bar in bars
            ]
            all_bars.extend(processed_data)

            # Small delay to avoid overwhelming the server
            await asyncio.sleep(0.1)

        print(f"Processed {len(all_bars)} bars efficiently")
```

### Connection Reuse Patterns

```python
class EfficientDataCollector:
    def __init__(self):
        self.client = None

    async def __aenter__(self):
        self.client = OHLCV()
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def collect_multiple_symbols(self, symbols: List[str]):
        """Reuse single connection for multiple operations"""
        results = {}

        for symbol in symbols:
            try:
                bars = await self.client.get_historical_ohlcv(symbol, "1D", 10)
                results[symbol] = bars
            except Exception as e:
                logging.error(f"Failed to fetch {symbol}: {e}")
                results[symbol] = None

        return results

# Usage
async def efficient_collection():
    symbols = ["NASDAQ:AAPL", "NASDAQ:GOOGL", "BINANCE:BTCUSDT"]

    async with EfficientDataCollector() as collector:
        results = await collector.collect_multiple_symbols(symbols)

        for symbol, bars in results.items():
            if bars:
                print(f"{symbol}: {len(bars)} bars collected")
```

## Integration Examples

### With DataExporter

```python
from tvkit.export import DataExporter

async def fetch_and_export_data():
    async with OHLCV() as client:
        # Fetch historical data
        bars = await client.get_historical_ohlcv("NASDAQ:AAPL", "1D", 30)

        # Export to multiple formats
        exporter = DataExporter()

        # Export to Polars DataFrame with technical indicators
        df = await exporter.to_polars(bars, add_analysis=True)
        print(f"DataFrame: {df.shape[0]} rows × {df.shape[1]} columns")

        # Export to files
        json_file = await exporter.to_json(bars, "./export/aapl_data.json")
        csv_file = await exporter.to_csv(bars, "./export/aapl_data.csv")

        print(f"Exported to: {json_file}, {csv_file}")
```

### Real-Time Trading Alerts

```python
async def price_alert_system():
    # Define alert thresholds
    alerts = {
        "NASDAQ:AAPL": {"upper": 200.0, "lower": 150.0},
        "BINANCE:BTCUSDT": {"upper": 50000.0, "lower": 30000.0}
    }

    async with OHLCV() as client:
        for symbol, thresholds in alerts.items():
            print(f"Monitoring {symbol} - Alert if < ${thresholds['lower']} or > ${thresholds['upper']}")

        # Monitor all symbols simultaneously
        async for trade_info in client.get_latest_trade_info(list(alerts.keys())):
            if trade_info.get('m') == 'qsd':
                data = trade_info.get('p', [{}])[1]
                symbol = data.get('n')
                price = data.get('lp')

                if symbol in alerts and price:
                    thresholds = alerts[symbol]
                    if price >= thresholds['upper']:
                        print(f"🚨 {symbol} HIGH ALERT: ${price} (threshold: ${thresholds['upper']})")
                    elif price <= thresholds['lower']:
                        print(f"🚨 {symbol} LOW ALERT: ${price} (threshold: ${thresholds['lower']})")
                    else:
                        print(f"✅ {symbol}: ${price} (within range)")
```

### Portfolio Value Tracking

```python
async def track_portfolio_value():
    portfolio = {
        "NASDAQ:AAPL": 10,      # 10 shares
        "NASDAQ:GOOGL": 5,      # 5 shares
        "BINANCE:BTCUSDT": 0.5  # 0.5 Bitcoin
    }

    async with OHLCV() as client:
        async for trade_info in client.get_latest_trade_info(list(portfolio.keys())):
            if trade_info.get('m') == 'qsd':
                data = trade_info.get('p', [{}])[1]
                symbol = data.get('n')
                price = data.get('lp')

                if symbol in portfolio and price:
                    shares = portfolio[symbol]
                    position_value = shares * price

                    print(f"{symbol}: {shares} × ${price} = ${position_value:,.2f}")

        # Calculate total portfolio value periodically
        total_value = 0
        for symbol, shares in portfolio.items():
            # Get latest price (implementation would cache recent prices)
            total_value += shares * 100  # Placeholder calculation

        print(f"Total Portfolio Value: ${total_value:,.2f}")
```

## Usage Examples

### Basic Real-Time Streaming

```python
import asyncio
from tvkit.api.chart.ohlcv import OHLCV
from tvkit.api.utils import convert_timestamp_to_iso

async def basic_streaming():
    """Basic example of real-time OHLCV streaming"""
    async with OHLCV() as client:
        print("Starting Bitcoin price stream...")

        count = 0
        async for bar in client.get_ohlcv("BINANCE:BTCUSDT", interval="1"):
            count += 1
            timestamp_iso = convert_timestamp_to_iso(bar.timestamp)

            print(f"Bar {count} [{timestamp_iso}]:")
            print(f"  Price: ${bar.close:,.2f}")
            print(f"  Volume: {bar.volume:,.0f}")
            print(f"  High: ${bar.high:,.2f} | Low: ${bar.low:,.2f}")
            print("-" * 50)

            # Limit to 10 bars for demo
            if count >= 10:
                break

asyncio.run(basic_streaming())
```

### Historical Data Analysis

```python
async def analyze_historical_data():
    """Fetch and analyze historical stock data"""
    async with OHLCV() as client:
        symbol = "NASDAQ:AAPL"
        print(f"Fetching 90 days of {symbol} data...")

        bars = await client.get_historical_ohlcv(symbol, "1D", 90)

        # Calculate basic statistics
        prices = [bar.close for bar in bars]
        volumes = [bar.volume for bar in bars]

        print(f"\n📊 90-Day Analysis for {symbol}:")
        print(f"  Total bars: {len(bars)}")
        print(f"  Price range: ${min(prices):.2f} - ${max(prices):.2f}")
        print(f"  Current price: ${prices[-1]:.2f}")
        print(f"  90-day change: {((prices[-1] - prices[0]) / prices[0] * 100):+.2f}%")
        print(f"  Average volume: {sum(volumes) / len(volumes):,.0f}")

        # Show recent price trend
        print(f"\n📈 Recent 5-day prices:")
        for bar in bars[-5:]:
            date = convert_timestamp_to_iso(bar.timestamp)[:10]
            change = ((bar.close - bar.open) / bar.open * 100)
            direction = "📈" if change >= 0 else "📉"
            print(f"  {date}: ${bar.close:.2f} {direction} {change:+.2f}%")

asyncio.run(analyze_historical_data())
```

### Multi-Asset Portfolio Monitoring

```python
async def monitor_diversified_portfolio():
    """Monitor a diversified portfolio across asset classes"""
    portfolio_symbols = [
        "NASDAQ:AAPL",      # Tech stock
        "NYSE:JNJ",         # Healthcare stock
        "BINANCE:BTCUSDT",  # Cryptocurrency
        "FOREX:EURUSD",     # Currency pair
        "COMEX:GC1!"        # Gold commodity
    ]

    async with OHLCV() as client:
        print("🎯 Starting diversified portfolio monitoring...")
        print(f"Tracking {len(portfolio_symbols)} assets")
        print("-" * 60)

        message_count = 0
        async for trade_info in client.get_latest_trade_info(portfolio_symbols):
            message_count += 1

            # Process quote symbol data
            if trade_info.get('m') == 'qsd':
                try:
                    data = trade_info.get('p', [{}])[1]
                    symbol = data.get('n', 'Unknown')
                    price = data.get('lp')
                    change = data.get('ch', 0)
                    change_pct = data.get('chp', 0)
                    volume = data.get('v', 0)

                    if price:
                        direction = "📈" if change >= 0 else "📉"
                        print(f"{direction} {symbol:<15} ${price:<10.2f} "
                              f"({change:+7.2f} | {change_pct:+6.2f}%) "
                              f"Vol: {volume:>10,.0f}")

                except Exception as e:
                    logging.debug(f"Error processing quote data: {e}")

            # Limit output for demo
            if message_count >= 50:
                print("\n✅ Portfolio monitoring demo completed")
                break

asyncio.run(monitor_diversified_portfolio())
```

### Price Alert System

```python
async def advanced_price_alerts():
    """Advanced price monitoring with multiple alert types"""

    class PriceAlert:
        def __init__(self, symbol: str, upper: float, lower: float):
            self.symbol = symbol
            self.upper_threshold = upper
            self.lower_threshold = lower
            self.last_price = None
            self.alerts_triggered = 0

    # Define alerts for different assets
    alerts = [
        PriceAlert("NASDAQ:AAPL", upper=200.0, lower=150.0),
        PriceAlert("BINANCE:BTCUSDT", upper=50000.0, lower=30000.0),
        PriceAlert("FOREX:EURUSD", upper=1.1000, lower=1.0500)
    ]

    alert_dict = {alert.symbol: alert for alert in alerts}

    async with OHLCV() as client:
        print("🚨 Advanced Price Alert System Active")
        for alert in alerts:
            print(f"  {alert.symbol}: Alert if < ${alert.lower_threshold} or > ${alert.upper_threshold}")
        print("-" * 70)

        async for trade_info in client.get_latest_trade_info(list(alert_dict.keys())):
            if trade_info.get('m') == 'qsd':
                data = trade_info.get('p', [{}])[1]
                symbol = data.get('n')
                current_price = data.get('lp')

                if symbol in alert_dict and current_price:
                    alert = alert_dict[symbol]
                    previous_price = alert.last_price
                    alert.last_price = current_price

                    # Check thresholds
                    if current_price >= alert.upper_threshold:
                        alert.alerts_triggered += 1
                        print(f"🔴 HIGH ALERT #{alert.alerts_triggered}: {symbol} at ${current_price}")

                    elif current_price <= alert.lower_threshold:
                        alert.alerts_triggered += 1
                        print(f"🔴 LOW ALERT #{alert.alerts_triggered}: {symbol} at ${current_price}")

                    else:
                        # Normal price movement
                        if previous_price:
                            change = current_price - previous_price
                            change_pct = (change / previous_price) * 100
                            direction = "↗️" if change >= 0 else "↘️"
                            print(f"✅ {symbol}: ${current_price:.4f} {direction} {change_pct:+.2f}%")
                        else:
                            print(f"📊 {symbol}: ${current_price:.4f} (baseline)")

# Run with keyboard interrupt handling
if __name__ == "__main__":
    try:
        asyncio.run(advanced_price_alerts())
    except KeyboardInterrupt:
        print("\n👋 Price alert system stopped by user")
```

## API Reference Summary

### Constructor and Context Management
- `__init__()`: Initialize OHLCV client
- `__aenter__()`: Async context manager entry
- `__aexit__()`: Async context manager exit with cleanup

### Core Streaming Methods
- `get_ohlcv()`: Real-time OHLCV bar streaming
- `get_historical_ohlcv()`: Historical OHLCV data retrieval
- `get_quote_data()`: Real-time quote data streaming
- `get_ohlcv_raw()`: Raw WebSocket message access
- `get_latest_trade_info()`: Multi-symbol trade information

### Internal Methods
- `_setup_services()`: Initialize WebSocket services

### Signal Handling
- `signal_handler()`: Graceful shutdown on keyboard interrupt

## Related Components

**Core Dependencies**:
- `tvkit.api.chart.services.ConnectionService`: WebSocket connection management
- `tvkit.api.chart.services.MessageService`: Protocol message handling
- `tvkit.api.chart.models.ohlcv`: Data model definitions
- `tvkit.api.chart.utils`: Validation and utility functions

**Integration Points**:
- **DataExporter**: Export OHLCV data to various formats
- **Scanner API**: Combine with market scanning for comprehensive analysis
- **Real-time Models**: Type-safe data structures for all responses

## Performance Notes

**Connection Efficiency**:
- Single WebSocket connection per client instance
- Connection reuse across multiple method calls within context
- Automatic connection management and cleanup

**Memory Management**:
- Streaming generators for memory-efficient real-time processing
- Configurable historical data chunk sizes
- Automatic resource cleanup on context exit

**Network Optimization**:
- Efficient multi-symbol subscriptions
- Protocol-level message compression
- Automatic heartbeat handling

---

**Note**: This documentation reflects tvkit v0.1.4. The OHLCV class is the primary interface for most users. For lower-level control, see ConnectionService and MessageService documentation.