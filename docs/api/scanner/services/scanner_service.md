# ScannerService Documentation

## Overview

The `ScannerService` is the primary service for interacting with TradingView's scanner API, providing comprehensive stock screening and market analysis capabilities. It handles HTTP requests to scanner endpoints with robust error handling, retry logic, and response validation, making it easy to scan 69+ global markets with 101+ financial metrics.

**Module Path**: `tvkit.api.scanner.services.scanner_service`

## Architecture

The ScannerService provides a high-level interface for TradingView's scanner API:

- **Market Screening**: Scan stocks across 69 global markets with comprehensive filtering
- **Async HTTP Client**: Built on httpx for high-performance async requests
- **Error Handling**: Comprehensive exception hierarchy with specific error types
- **Retry Logic**: Exponential backoff for resilient API interactions
- **Response Validation**: Pydantic-based validation for type-safe data handling
- **Context Manager**: Safe resource management with automatic cleanup

## Exception Hierarchy

### Base Exceptions

```python
class ScannerServiceError(Exception):
    """Base exception for Scanner Service errors."""
    pass

class ScannerConnectionError(ScannerServiceError):
    """Raised when connection to scanner API fails."""
    pass

class ScannerAPIError(ScannerServiceError):
    """Raised when scanner API returns an error response."""
    pass

class ScannerValidationError(ScannerServiceError):
    """Raised when response validation fails."""
    pass
```

**Error Categories**:
- **ScannerConnectionError**: Network timeouts, connection failures, DNS issues
- **ScannerAPIError**: HTTP errors (4xx, 5xx), malformed responses, API rate limits
- **ScannerValidationError**: Invalid response structure, missing fields, type mismatches

## Class Definition

### ScannerService

```python
class ScannerService:
    """
    Service for interacting with TradingView's scanner API.

    This service handles POST requests to scanner endpoints with proper
    error handling, retry logic, and response validation.
    """
```

#### Constructor

```python
def __init__(
    self,
    base_url: str = "https://scanner.tradingview.com",
    timeout: float = 30.0,
    max_retries: int = 3,
    user_agent: str = "tvkit/1.0",
) -> None
```

**Description**: Initialize the scanner service with configurable parameters for API interactions.

**Parameters**:
- `base_url` (str): Base URL for the scanner API (default: "https://scanner.tradingview.com")
- `timeout` (float): Request timeout in seconds (default: 30.0)
- `max_retries` (int): Maximum retry attempts for failed requests (default: 3)
- `user_agent` (str): User agent string for HTTP requests (default: "tvkit/1.0")

**Configuration Details**:
- **Default Headers**: Content-Type: application/json, Accept: application/json
- **Timeout Strategy**: Individual request timeout (not total operation time)
- **Retry Strategy**: Exponential backoff (2^attempt seconds between retries)
- **URL Normalization**: Automatically strips trailing slashes from base_url

**Usage Example**:
```python
# Default configuration
service = ScannerService()

# Custom configuration for production
service = ScannerService(
    timeout=60.0,           # Longer timeout for complex queries
    max_retries=5,          # More retries for reliability
    user_agent="MyApp/2.0"  # Custom user agent
)
```

## Core Methods

### Market Scanning

#### scan_market()

```python
async def scan_market(
    self,
    market: Market,
    request: ScannerRequest,
    label_product: str = "markets-screener",
) -> ScannerResponse
```

**Description**: Scan a specific market using the TradingView scanner API with comprehensive error handling and response validation.

**Parameters**:
- `market` (Market): Market to scan using Market enum (e.g., Market.THAILAND, Market.AMERICA)
- `request` (ScannerRequest): Scanner request configuration with columns, filters, sorting
- `label_product` (str): Label product parameter for API tracking (default: "markets-screener")

**Returns**: `ScannerResponse` object containing:
- `data` (List[StockData]): List of stocks matching the criteria
- `total_count` (int): Total number of stocks in the market
- `metadata` (dict): Response metadata and pagination info

**Market Support**: Works with all 69 supported markets:
- **North America**: Market.AMERICA, Market.CANADA
- **Europe**: Market.GERMANY, Market.FRANCE, Market.UK, Market.NETHERLANDS
- **Asia Pacific**: Market.THAILAND, Market.JAPAN, Market.SINGAPORE, Market.KOREA
- **And 60+ more markets across all regions

**Error Handling**:
- `ScannerConnectionError`: Network connectivity issues
- `ScannerAPIError`: HTTP errors or invalid API responses
- `ScannerValidationError`: Response structure validation failures
- `ValueError`: Invalid market parameter

**Usage Example**:
```python
from tvkit.api.scanner.services import ScannerService
from tvkit.api.scanner.markets import Market
from tvkit.api.scanner.models import create_scanner_request, ColumnSets

async def scan_thai_market():
    service = ScannerService()

    # Create request for top 50 stocks by market cap
    request = create_scanner_request(
        columns=ColumnSets.FUNDAMENTALS,
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=50
    )

    try:
        response = await service.scan_market(Market.THAILAND, request)
        print(f"Found {len(response.data)} Thai stocks")

        # Display top 5 companies
        for i, stock in enumerate(response.data[:5]):
            print(f"{i+1}. {stock.name}: ${stock.market_cap_basic:,.0f} market cap")

    except ScannerConnectionError as e:
        print(f"Connection failed: {e}")
    except ScannerAPIError as e:
        print(f"API error: {e}")
```

#### scan_market_by_id()

```python
async def scan_market_by_id(
    self,
    market_id: str,
    request: ScannerRequest,
    label_product: str = "markets-screener",
) -> ScannerResponse
```

**Description**: Scan a market using string identifier instead of Market enum, providing flexibility for dynamic market selection.

**Parameters**:
- `market_id` (str): Market identifier string (e.g., 'thailand', 'america', 'japan')
- `request` (ScannerRequest): Scanner request configuration
- `label_product` (str): Label product parameter (default: "markets-screener")

**Returns**: `ScannerResponse` object with scanned market data

**Market ID Validation**:
- Validates market_id against supported markets before processing
- Converts valid string IDs to Market enum internally
- Provides clear error messages for invalid market identifiers

**Use Cases**:
- **Dynamic Market Selection**: When market is determined at runtime
- **String-Based Configuration**: Loading market names from config files
- **User Input Processing**: Handling market names from user interfaces
- **Batch Processing**: Iterating through market lists with string identifiers

**Usage Example**:
```python
async def scan_markets_dynamically():
    service = ScannerService()
    request = create_scanner_request(columns=ColumnSets.BASIC)

    # Markets from configuration or user input
    market_names = ["thailand", "singapore", "japan", "korea"]

    results = {}
    for market_name in market_names:
        try:
            response = await service.scan_market_by_id(market_name, request)
            results[market_name] = len(response.data)
            print(f"✅ {market_name.title()}: {len(response.data)} stocks")
        except ValueError as e:
            print(f"❌ Invalid market '{market_name}': {e}")
        except Exception as e:
            print(f"⚠️  Error scanning {market_name}: {e}")

    return results
```

### Internal Methods

#### _make_scanner_request()

```python
async def _make_scanner_request(
    self,
    endpoint: str,
    request: ScannerRequest,
    params: Optional[Dict[str, str]] = None,
) -> ScannerResponse
```

**Description**: Internal method handling the actual HTTP request with comprehensive retry logic and error handling.

**Implementation Details**:
- **Retry Logic**: Exponential backoff (2^attempt seconds)
- **Error Classification**: Distinguishes retryable vs non-retryable errors
- **Response Validation**: Uses Pydantic models for type-safe parsing
- **Connection Management**: Automatic client lifecycle management

**Retry Behavior**:
- **Retryable Errors**: TimeoutException, ConnectError, RequestError
- **Non-Retryable Errors**: ScannerAPIError, ScannerValidationError
- **Backoff Pattern**: 1s, 2s, 4s, 8s... (exponential)
- **Maximum Attempts**: Configurable via max_retries parameter

### Context Manager Support

#### __aenter__() and __aexit__()

```python
async def __aenter__(self) -> "ScannerService"
async def __aexit__(self, exc_type, exc_val, exc_tb) -> None
```

**Description**: Provides async context manager support for resource management.

**Usage Pattern**:
```python
async with ScannerService() as service:
    response = await service.scan_market(Market.THAILAND, request)
    # Automatic cleanup handled here
```

## Helper Functions

### create_comprehensive_request()

```python
def create_comprehensive_request(
    sort_by: str = "name",
    sort_order: Literal["asc", "desc"] = "asc",
    range_start: int = 0,
    range_end: int = 1000,
    language: str = "en",
) -> ScannerRequest
```

**Description**: Creates a scanner request with the complete set of TradingView columns for maximum data availability.

**Parameters**:
- `sort_by` (str): Field to sort results by (default: "name")
- `sort_order` (Literal["asc", "desc"]): Sort direction (default: "asc")
- `range_start` (int): Starting index for results (default: 0)
- `range_end` (int): Ending index for results, exclusive (default: 1000)
- `language` (str): Language code for localization (default: "en")

**Column Set**: Uses `ColumnSets.COMPREHENSIVE_FULL` which includes:
- **Basic Data**: Symbol, name, price, change, volume
- **Fundamentals**: Market cap, P/E ratio, revenue, earnings
- **Technical Indicators**: RSI, MACD, moving averages, momentum
- **Performance Metrics**: YTD, 1M, 3M, 6M, 1Y returns
- **Valuation Ratios**: P/B, EV/Revenue, PEG ratio, Price/Sales
- **Financial Health**: Debt ratios, current ratio, ROE, ROA
- **Dividends**: Yield, payout ratio, growth rate
- **And 80+ additional columns**

**Sort Field Options**:
- **Alphabetical**: "name", "description"
- **Price Data**: "close", "change", "change_abs", "volume"
- **Market Metrics**: "market_cap_basic", "market_cap_calc"
- **Valuation**: "price_earnings_ttm", "price_book_fq", "enterprise_value_ebitda_ttm"
- **Performance**: "perf_y", "perf_ytd", "perf_6m", "perf_3m", "perf_1m"
- **Financial**: "total_revenue", "net_income", "debt_to_equity"

**Usage Examples**:
```python
# Top 50 companies by market cap
request = create_comprehensive_request(
    sort_by="market_cap_basic",
    sort_order="desc",
    range_end=50
)

# Best performing stocks this year
request = create_comprehensive_request(
    sort_by="perf_ytd",
    sort_order="desc",
    range_end=100
)

# Most undervalued stocks by P/E ratio
request = create_comprehensive_request(
    sort_by="price_earnings_ttm",
    sort_order="asc",
    range_end=25
)

# Highest dividend yielding stocks
request = create_comprehensive_request(
    sort_by="dividend_yield_recent",
    sort_order="desc",
    range_end=30
)
```

## Error Handling Patterns

### Connection Error Recovery

```python
async def robust_market_scanning():
    """Implement robust scanning with comprehensive error handling"""

    service = ScannerService(
        timeout=60.0,      # Longer timeout for complex queries
        max_retries=5      # More aggressive retry strategy
    )

    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=100
    )

    markets_to_scan = [Market.THAILAND, Market.SINGAPORE, Market.JAPAN]
    results = {}

    for market in markets_to_scan:
        try:
            print(f"Scanning {market.value}...")
            response = await service.scan_market(market, request)

            results[market.value] = {
                "success": True,
                "stocks_found": len(response.data),
                "top_stock": response.data[0].name if response.data else None
            }
            print(f"✅ {market.value}: {len(response.data)} stocks")

        except ScannerConnectionError as e:
            results[market.value] = {"success": False, "error": f"Connection: {e}"}
            print(f"🔴 {market.value}: Connection failed - {e}")

        except ScannerAPIError as e:
            results[market.value] = {"success": False, "error": f"API: {e}"}
            print(f"🔴 {market.value}: API error - {e}")

        except ScannerValidationError as e:
            results[market.value] = {"success": False, "error": f"Validation: {e}"}
            print(f"🔴 {market.value}: Data validation failed - {e}")

        except Exception as e:
            results[market.value] = {"success": False, "error": f"Unknown: {e}"}
            print(f"🔴 {market.value}: Unexpected error - {e}")

    # Summary
    successful = sum(1 for r in results.values() if r["success"])
    total = len(results)
    print(f"\n📊 Summary: {successful}/{total} markets scanned successfully")

    return results
```

### API Rate Limit Handling

```python
import asyncio
from typing import List

async def batch_market_scanning_with_rate_limits():
    """Scan multiple markets with rate limit handling"""

    service = ScannerService(max_retries=3)
    request = create_comprehensive_request(range_end=50)

    # All available markets
    markets = [
        Market.AMERICA, Market.CANADA, Market.UK, Market.GERMANY,
        Market.FRANCE, Market.NETHERLANDS, Market.ITALY, Market.SPAIN,
        Market.THAILAND, Market.JAPAN, Market.SINGAPORE, Market.KOREA
    ]

    results = {}
    batch_size = 3  # Process 3 markets at a time
    delay_between_batches = 2.0  # 2-second delay between batches

    for i in range(0, len(markets), batch_size):
        batch = markets[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1}: {[m.value for m in batch]}")

        # Process batch concurrently
        batch_tasks = []
        for market in batch:
            task = scan_single_market_with_fallback(service, market, request)
            batch_tasks.append(task)

        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        # Process batch results
        for market, result in zip(batch, batch_results):
            if isinstance(result, Exception):
                results[market.value] = {"error": str(result)}
                print(f"❌ {market.value}: {result}")
            else:
                results[market.value] = result
                print(f"✅ {market.value}: {result['count']} stocks")

        # Rate limit delay between batches
        if i + batch_size < len(markets):
            print(f"Waiting {delay_between_batches}s before next batch...")
            await asyncio.sleep(delay_between_batches)

    return results

async def scan_single_market_with_fallback(service, market, request):
    """Scan single market with intelligent fallback"""
    try:
        response = await service.scan_market(market, request)
        return {
            "count": len(response.data),
            "top_company": response.data[0].name if response.data else None,
            "avg_market_cap": sum(s.market_cap_basic or 0 for s in response.data) / len(response.data) if response.data else 0
        }
    except ScannerAPIError as e:
        if "rate limit" in str(e).lower():
            print(f"Rate limit hit for {market.value}, waiting 30s...")
            await asyncio.sleep(30)
            # Retry once after rate limit
            response = await service.scan_market(market, request)
            return {"count": len(response.data), "retry": True}
        raise
```

### Response Validation Handling

```python
async def validate_scanner_response_data():
    """Comprehensive response validation and data quality checks"""

    service = ScannerService()
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=20
    )

    try:
        response = await service.scan_market(Market.AMERICA, request)

        # Validate response structure
        print(f"Response received: {len(response.data)} stocks")

        # Data quality validation
        quality_report = {
            "total_stocks": len(response.data),
            "stocks_with_market_cap": 0,
            "stocks_with_pe_ratio": 0,
            "stocks_with_volume": 0,
            "price_range": {"min": float('inf'), "max": 0},
            "invalid_data_count": 0
        }

        for stock in response.data:
            # Market cap validation
            if stock.market_cap_basic and stock.market_cap_basic > 0:
                quality_report["stocks_with_market_cap"] += 1

            # P/E ratio validation
            if stock.price_earnings_ttm and stock.price_earnings_ttm > 0:
                quality_report["stocks_with_pe_ratio"] += 1

            # Volume validation
            if stock.volume and stock.volume > 0:
                quality_report["stocks_with_volume"] += 1

            # Price range tracking
            if stock.close:
                quality_report["price_range"]["min"] = min(quality_report["price_range"]["min"], stock.close)
                quality_report["price_range"]["max"] = max(quality_report["price_range"]["max"], stock.close)

            # Basic data integrity check
            if not stock.name or not stock.close:
                quality_report["invalid_data_count"] += 1
                print(f"⚠️  Invalid data for stock: {stock.name or 'Unknown'}")

        # Report data quality
        print(f"\n📊 Data Quality Report:")
        print(f"  Stocks with market cap: {quality_report['stocks_with_market_cap']}/{quality_report['total_stocks']}")
        print(f"  Stocks with P/E ratio: {quality_report['stocks_with_pe_ratio']}/{quality_report['total_stocks']}")
        print(f"  Stocks with volume data: {quality_report['stocks_with_volume']}/{quality_report['total_stocks']}")
        print(f"  Price range: ${quality_report['price_range']['min']:.2f} - ${quality_report['price_range']['max']:.2f}")
        print(f"  Invalid data entries: {quality_report['invalid_data_count']}")

        return quality_report

    except ScannerValidationError as e:
        print(f"Validation Error: {e}")
        print("This might indicate:")
        print("  - TradingView API response format changed")
        print("  - Network corruption of response data")
        print("  - Incompatible column configuration")

        # Fallback with basic columns
        print("\nTrying fallback with basic columns...")
        basic_request = create_scanner_request(columns=ColumnSets.BASIC)
        response = await service.scan_market(Market.AMERICA, basic_request)
        print(f"Fallback successful: {len(response.data)} stocks with basic data")

        return {"fallback_used": True, "basic_data_count": len(response.data)}
```

## Performance Optimization

### Concurrent Market Scanning

```python
import asyncio
from typing import Dict, List

async def concurrent_multi_market_analysis():
    """Efficiently scan multiple markets concurrently"""

    # Markets grouped by region for logical organization
    regions = {
        "North America": [Market.AMERICA, Market.CANADA],
        "Europe": [Market.UK, Market.GERMANY, Market.FRANCE, Market.NETHERLANDS],
        "Asia Pacific": [Market.THAILAND, Market.JAPAN, Market.SINGAPORE, Market.KOREA],
        "Emerging Markets": [Market.INDIA, Market.BRAZIL, Market.MEXICO, Market.SOUTH_AFRICA]
    }

    async def scan_region(region_name: str, markets: List[Market]) -> Dict:
        """Scan all markets in a region concurrently"""
        service = ScannerService(timeout=45.0)
        request = create_comprehensive_request(
            sort_by="market_cap_basic",
            sort_order="desc",
            range_end=10  # Top 10 per market for speed
        )

        print(f"🌍 Scanning {region_name} ({len(markets)} markets)...")

        # Create concurrent tasks for all markets in region
        tasks = []
        for market in markets:
            task = asyncio.create_task(
                scan_market_with_metadata(service, market, request),
                name=f"scan_{market.value}"
            )
            tasks.append((market, task))

        # Wait for all markets in region to complete
        results = {}
        completed_tasks = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True
        )

        for (market, _), result in zip(tasks, completed_tasks):
            if isinstance(result, Exception):
                results[market.value] = {"error": str(result)}
            else:
                results[market.value] = result

        return results

    # Scan all regions concurrently
    region_tasks = []
    for region_name, markets in regions.items():
        task = asyncio.create_task(
            scan_region(region_name, markets),
            name=f"region_{region_name.lower().replace(' ', '_')}"
        )
        region_tasks.append((region_name, task))

    # Collect results from all regions
    all_results = {}
    start_time = asyncio.get_event_loop().time()

    for region_name, task in region_tasks:
        region_results = await task
        all_results[region_name] = region_results

        # Progress reporting
        successful = sum(1 for r in region_results.values() if "error" not in r)
        total = len(region_results)
        print(f"✅ {region_name}: {successful}/{total} markets completed")

    end_time = asyncio.get_event_loop().time()
    total_time = end_time - start_time

    # Summary statistics
    total_markets = sum(len(results) for results in all_results.values())
    successful_markets = sum(
        sum(1 for r in results.values() if "error" not in r)
        for results in all_results.values()
    )

    print(f"\n📈 Global Market Scan Complete:")
    print(f"  Time taken: {total_time:.2f} seconds")
    print(f"  Markets scanned: {successful_markets}/{total_markets}")
    print(f"  Average time per market: {total_time/total_markets:.2f}s")

    return all_results

async def scan_market_with_metadata(service, market, request):
    """Scan single market and return enriched metadata"""
    try:
        response = await service.scan_market(market, request)

        # Calculate market statistics
        stocks = response.data
        if not stocks:
            return {"count": 0}

        market_caps = [s.market_cap_basic for s in stocks if s.market_cap_basic]
        volumes = [s.volume for s in stocks if s.volume]

        return {
            "count": len(stocks),
            "largest_company": stocks[0].name,
            "total_market_cap": sum(market_caps) if market_caps else 0,
            "avg_volume": sum(volumes) / len(volumes) if volumes else 0,
            "price_range": {
                "min": min(s.close for s in stocks if s.close),
                "max": max(s.close for s in stocks if s.close)
            } if any(s.close for s in stocks) else None
        }
    except Exception as e:
        raise e  # Let parent handle the exception
```

### Request Optimization Strategies

```python
class OptimizedScannerService(ScannerService):
    """Enhanced ScannerService with optimization features"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._response_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL

    async def scan_market_cached(
        self,
        market: Market,
        request: ScannerRequest,
        use_cache: bool = True
    ) -> ScannerResponse:
        """Scan market with intelligent caching"""

        # Create cache key from request parameters
        cache_key = f"{market.value}_{hash(request.model_dump_json())}"

        # Check cache if enabled
        if use_cache and cache_key in self._response_cache:
            cached_response, timestamp = self._response_cache[cache_key]
            if asyncio.get_event_loop().time() - timestamp < self._cache_ttl:
                print(f"📋 Cache hit for {market.value}")
                return cached_response

        # Make API request
        print(f"🌐 API request for {market.value}")
        response = await self.scan_market(market, request)

        # Cache the response
        if use_cache:
            self._response_cache[cache_key] = (response, asyncio.get_event_loop().time())

            # Cache cleanup (remove expired entries)
            current_time = asyncio.get_event_loop().time()
            expired_keys = [
                key for key, (_, timestamp) in self._response_cache.items()
                if current_time - timestamp >= self._cache_ttl
            ]
            for key in expired_keys:
                del self._response_cache[key]

        return response

    def get_cache_stats(self) -> Dict:
        """Get cache performance statistics"""
        current_time = asyncio.get_event_loop().time()
        active_entries = sum(
            1 for _, timestamp in self._response_cache.values()
            if current_time - timestamp < self._cache_ttl
        )

        return {
            "total_cached": len(self._response_cache),
            "active_entries": active_entries,
            "cache_ttl": self._cache_ttl
        }
```

## Integration Examples

### With Market Analysis

```python
from tvkit.api.scanner.markets import Market, MarketRegion, get_markets_by_region

async def comprehensive_market_analysis():
    """Perform comprehensive analysis across market regions"""

    service = ScannerService()

    # Analyze different market segments
    analysis_configs = {
        "large_cap": {
            "request": create_comprehensive_request(
                sort_by="market_cap_basic",
                sort_order="desc",
                range_end=50
            ),
            "description": "Top 50 companies by market cap"
        },
        "high_growth": {
            "request": create_comprehensive_request(
                sort_by="perf_ytd",
                sort_order="desc",
                range_end=30
            ),
            "description": "Top 30 YTD performers"
        },
        "value_stocks": {
            "request": create_comprehensive_request(
                sort_by="price_earnings_ttm",
                sort_order="asc",
                range_end=25
            ),
            "description": "25 most undervalued by P/E"
        },
        "dividend_stocks": {
            "request": create_comprehensive_request(
                sort_by="dividend_yield_recent",
                sort_order="desc",
                range_end=20
            ),
            "description": "Top 20 dividend yielders"
        }
    }

    # Target markets for analysis
    target_markets = [Market.AMERICA, Market.UK, Market.JAPAN, Market.GERMANY]

    results = {}

    for market in target_markets:
        print(f"\n🏛️  Analyzing {market.value.title()} Market")
        print("=" * 50)

        market_results = {}

        for segment_name, config in analysis_configs.items():
            try:
                response = await service.scan_market(market, config["request"])

                # Extract key insights
                stocks = response.data
                if stocks:
                    insights = {
                        "count": len(stocks),
                        "description": config["description"],
                        "top_stock": {
                            "name": stocks[0].name,
                            "price": stocks[0].close,
                            "market_cap": stocks[0].market_cap_basic
                        },
                        "sector_breakdown": analyze_sector_distribution(stocks),
                        "avg_metrics": calculate_average_metrics(stocks)
                    }

                    market_results[segment_name] = insights
                    print(f"✅ {segment_name}: {insights['top_stock']['name']} leads with ${insights['top_stock']['market_cap']:,.0f}M cap")
                else:
                    market_results[segment_name] = {"count": 0, "error": "No data"}
                    print(f"❌ {segment_name}: No data available")

            except Exception as e:
                market_results[segment_name] = {"error": str(e)}
                print(f"❌ {segment_name}: Error - {e}")

        results[market.value] = market_results

    return results

def analyze_sector_distribution(stocks):
    """Analyze sector distribution in stock list"""
    sectors = {}
    for stock in stocks:
        sector = stock.sector or "Unknown"
        sectors[sector] = sectors.get(sector, 0) + 1

    # Return top 3 sectors
    return dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:3])

def calculate_average_metrics(stocks):
    """Calculate average financial metrics"""
    valid_pe = [s.price_earnings_ttm for s in stocks if s.price_earnings_ttm and s.price_earnings_ttm > 0]
    valid_pb = [s.price_book_fq for s in stocks if s.price_book_fq and s.price_book_fq > 0]
    valid_div = [s.dividend_yield_recent for s in stocks if s.dividend_yield_recent and s.dividend_yield_recent > 0]

    return {
        "avg_pe_ratio": sum(valid_pe) / len(valid_pe) if valid_pe else None,
        "avg_pb_ratio": sum(valid_pb) / len(valid_pb) if valid_pb else None,
        "avg_dividend_yield": sum(valid_div) / len(valid_div) if valid_div else None,
        "sample_sizes": {
            "pe_data": len(valid_pe),
            "pb_data": len(valid_pb),
            "dividend_data": len(valid_div)
        }
    }
```

### With Data Export Integration

```python
from tvkit.export import DataExporter
import polars as pl

async def scan_and_export_market_data():
    """Scan market data and export to multiple formats"""

    service = ScannerService()
    exporter = DataExporter()

    # Comprehensive scan of US market
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=500  # Top 500 companies
    )

    print("📊 Scanning US market for top 500 companies...")
    response = await service.scan_market(Market.AMERICA, request)

    print(f"✅ Retrieved {len(response.data)} companies")

    # Convert to structured format for export
    export_data = []
    for stock in response.data:
        export_data.append({
            "symbol": stock.name,
            "company_name": stock.description or stock.name,
            "price": stock.close,
            "market_cap": stock.market_cap_basic,
            "pe_ratio": stock.price_earnings_ttm,
            "pb_ratio": stock.price_book_fq,
            "dividend_yield": stock.dividend_yield_recent,
            "sector": stock.sector,
            "volume": stock.volume,
            "ytd_performance": stock.perf_ytd,
            "revenue_ttm": stock.total_revenue,
            "net_income": stock.net_income,
            "debt_to_equity": stock.debt_to_equity
        })

    # Create Polars DataFrame
    df = pl.DataFrame(export_data)

    # Export to multiple formats
    timestamp = asyncio.get_event_loop().time()

    # JSON export
    json_path = f"./export/us_market_scan_{int(timestamp)}.json"
    await exporter.to_json(export_data, json_path, include_metadata=True)

    # CSV export
    csv_path = f"./export/us_market_scan_{int(timestamp)}.csv"
    df.write_csv(csv_path)

    # Parquet export for efficient storage
    parquet_path = f"./export/us_market_scan_{int(timestamp)}.parquet"
    df.write_parquet(parquet_path)

    print(f"📁 Data exported to:")
    print(f"   JSON: {json_path}")
    print(f"   CSV: {csv_path}")
    print(f"   Parquet: {parquet_path}")

    # Generate summary report
    summary = {
        "total_companies": len(export_data),
        "avg_market_cap": df.select(pl.col("market_cap").mean()).item(),
        "avg_pe_ratio": df.select(pl.col("pe_ratio").mean()).item(),
        "sectors": df.group_by("sector").count().sort("count", descending=True).head(10),
        "top_performers": df.sort("ytd_performance", descending=True).head(5),
        "export_timestamp": timestamp
    }

    # Export summary
    summary_path = f"./export/summary_{int(timestamp)}.json"
    with open(summary_path, 'w') as f:
        import json
        json.dump(summary, f, indent=2, default=str)

    print(f"📈 Summary report: {summary_path}")

    return {
        "companies_exported": len(export_data),
        "files_created": [json_path, csv_path, parquet_path, summary_path],
        "summary": summary
    }
```

## Usage Examples

### Basic Market Scanning

```python
import asyncio
from tvkit.api.scanner.services import ScannerService, create_comprehensive_request
from tvkit.api.scanner.markets import Market

async def basic_market_scan():
    """Basic example of scanning a single market"""

    # Initialize service with default settings
    service = ScannerService()

    # Create request for top 20 companies by market cap
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=20
    )

    try:
        print("🔍 Scanning Thai market for top 20 companies by market cap...")
        response = await service.scan_market(Market.THAILAND, request)

        print(f"✅ Found {len(response.data)} companies\n")

        # Display results
        for i, stock in enumerate(response.data, 1):
            market_cap = f"${stock.market_cap_basic:,.0f}M" if stock.market_cap_basic else "N/A"
            pe_ratio = f"{stock.price_earnings_ttm:.2f}" if stock.price_earnings_ttm else "N/A"

            print(f"{i:2d}. {stock.name}")
            print(f"     Price: ${stock.close:.2f} | Market Cap: {market_cap} | P/E: {pe_ratio}")
            print(f"     Sector: {stock.sector or 'Unknown'}")
            print()

    except Exception as e:
        print(f"❌ Error: {e}")

# Run the example
asyncio.run(basic_market_scan())
```

### Multi-Market Comparison

```python
async def multi_market_comparison():
    """Compare markets across different regions"""

    service = ScannerService(timeout=45.0)

    # Markets to compare
    markets_to_compare = {
        "🇺🇸 United States": Market.AMERICA,
        "🇬🇧 United Kingdom": Market.UK,
        "🇩🇪 Germany": Market.GERMANY,
        "🇯🇵 Japan": Market.JAPAN,
        "🇹🇭 Thailand": Market.THAILAND,
        "🇸🇬 Singapore": Market.SINGAPORE
    }

    # Request top 10 companies by market cap from each market
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=10
    )

    print("🌍 Global Market Comparison - Top 10 Companies by Market Cap")
    print("=" * 70)

    comparison_results = {}

    for market_name, market_enum in markets_to_compare.items():
        try:
            print(f"\n{market_name}")
            print("-" * 40)

            response = await service.scan_market(market_enum, request)
            stocks = response.data

            if stocks:
                # Market statistics
                total_market_cap = sum(s.market_cap_basic or 0 for s in stocks)
                avg_pe = sum(s.price_earnings_ttm or 0 for s in stocks if s.price_earnings_ttm) / len([s for s in stocks if s.price_earnings_ttm])

                comparison_results[market_name] = {
                    "companies": len(stocks),
                    "largest_company": stocks[0].name,
                    "largest_market_cap": stocks[0].market_cap_basic,
                    "total_top10_market_cap": total_market_cap,
                    "avg_pe_ratio": avg_pe
                }

                # Display top 3 companies
                for i, stock in enumerate(stocks[:3], 1):
                    market_cap = f"${stock.market_cap_basic:,.0f}M" if stock.market_cap_basic else "N/A"
                    print(f"  {i}. {stock.name} - {market_cap}")

                print(f"\n  📈 Market Leader: {stocks[0].name}")
                print(f"  💰 Combined Top 10 Market Cap: ${total_market_cap:,.0f}M")
                print(f"  📊 Average P/E Ratio: {avg_pe:.2f}")
            else:
                comparison_results[market_name] = {"error": "No data available"}
                print("  ❌ No data available")

        except Exception as e:
            comparison_results[market_name] = {"error": str(e)}
            print(f"  ❌ Error: {e}")

    # Summary comparison
    print(f"\n🏆 Market Leaders Summary:")
    print("=" * 50)

    successful_markets = {k: v for k, v in comparison_results.items() if "error" not in v}

    if successful_markets:
        # Largest company globally
        largest_global = max(
            successful_markets.items(),
            key=lambda x: x[1]["largest_market_cap"] or 0
        )
        print(f"🥇 Largest Company: {largest_global[1]['largest_company']} ({largest_global[0]})")
        print(f"   Market Cap: ${largest_global[1]['largest_market_cap']:,.0f}M")

        # Market with highest combined market cap
        strongest_market = max(
            successful_markets.items(),
            key=lambda x: x[1]["total_top10_market_cap"]
        )
        print(f"🏛️  Strongest Market: {strongest_market[0]}")
        print(f"   Combined Top 10 Market Cap: ${strongest_market[1]['total_top10_market_cap']:,.0f}M")

    return comparison_results

# Run the comparison
asyncio.run(multi_market_comparison())
```

### Advanced Filtering and Analysis

```python
async def advanced_stock_screening():
    """Advanced stock screening with custom criteria"""

    service = ScannerService()

    # Define screening criteria
    screening_strategies = {
        "Growth Stocks": {
            "description": "High growth companies with strong performance",
            "request": create_comprehensive_request(
                sort_by="perf_ytd",
                sort_order="desc",
                range_end=30
            )
        },
        "Value Stocks": {
            "description": "Undervalued companies with low P/E ratios",
            "request": create_comprehensive_request(
                sort_by="price_earnings_ttm",
                sort_order="asc",
                range_end=25
            )
        },
        "Dividend Champions": {
            "description": "High dividend yielding companies",
            "request": create_comprehensive_request(
                sort_by="dividend_yield_recent",
                sort_order="desc",
                range_end=20
            )
        },
        "Market Giants": {
            "description": "Largest companies by market capitalization",
            "request": create_comprehensive_request(
                sort_by="market_cap_basic",
                sort_order="desc",
                range_end=15
            )
        }
    }

    # Target market for screening
    target_market = Market.AMERICA

    print(f"🎯 Advanced Stock Screening - {target_market.value.title()} Market")
    print("=" * 60)

    screening_results = {}

    for strategy_name, strategy_config in screening_strategies.items():
        print(f"\n📊 {strategy_name}")
        print(f"    {strategy_config['description']}")
        print("-" * 50)

        try:
            response = await service.scan_market(target_market, strategy_config['request'])
            stocks = response.data

            if stocks:
                # Analyze the screening results
                analysis = analyze_screening_results(stocks, strategy_name)
                screening_results[strategy_name] = analysis

                # Display top picks
                print(f"✅ Found {len(stocks)} qualifying stocks")
                print(f"📈 Top 5 Picks:")

                for i, stock in enumerate(stocks[:5], 1):
                    metrics = format_stock_metrics(stock, strategy_name)
                    print(f"  {i}. {stock.name}")
                    print(f"     {metrics}")

                # Strategy-specific insights
                print(f"\n💡 {strategy_name} Insights:")
                for key, value in analysis["insights"].items():
                    print(f"     {key}: {value}")
            else:
                screening_results[strategy_name] = {"error": "No qualifying stocks found"}
                print("❌ No qualifying stocks found")

        except Exception as e:
            screening_results[strategy_name] = {"error": str(e)}
            print(f"❌ Error: {e}")

    return screening_results

def analyze_screening_results(stocks, strategy_name):
    """Analyze screening results based on strategy type"""
    if not stocks:
        return {"count": 0}

    analysis = {
        "count": len(stocks),
        "top_pick": stocks[0].name,
        "sectors": {},
        "insights": {}
    }

    # Sector distribution
    for stock in stocks:
        sector = stock.sector or "Unknown"
        analysis["sectors"][sector] = analysis["sectors"].get(sector, 0) + 1

    # Strategy-specific analysis
    if strategy_name == "Growth Stocks":
        ytd_perfs = [s.perf_ytd for s in stocks if s.perf_ytd]
        if ytd_perfs:
            analysis["insights"]["Average YTD Return"] = f"{sum(ytd_perfs)/len(ytd_perfs):.1f}%"
            analysis["insights"]["Best Performer"] = f"{max(ytd_perfs):.1f}%"

    elif strategy_name == "Value Stocks":
        pe_ratios = [s.price_earnings_ttm for s in stocks if s.price_earnings_ttm and s.price_earnings_ttm > 0]
        if pe_ratios:
            analysis["insights"]["Average P/E Ratio"] = f"{sum(pe_ratios)/len(pe_ratios):.2f}"
            analysis["insights"]["Lowest P/E"] = f"{min(pe_ratios):.2f}"

    elif strategy_name == "Dividend Champions":
        div_yields = [s.dividend_yield_recent for s in stocks if s.dividend_yield_recent]
        if div_yields:
            analysis["insights"]["Average Dividend Yield"] = f"{sum(div_yields)/len(div_yields):.2f}%"
            analysis["insights"]["Highest Yield"] = f"{max(div_yields):.2f}%"

    elif strategy_name == "Market Giants":
        market_caps = [s.market_cap_basic for s in stocks if s.market_cap_basic]
        if market_caps:
            analysis["insights"]["Combined Market Cap"] = f"${sum(market_caps):,.0f}M"
            analysis["insights"]["Average Market Cap"] = f"${sum(market_caps)/len(market_caps):,.0f}M"

    return analysis

def format_stock_metrics(stock, strategy_name):
    """Format stock metrics based on screening strategy"""
    price = f"${stock.close:.2f}" if stock.close else "N/A"

    if strategy_name == "Growth Stocks":
        ytd = f"{stock.perf_ytd:.1f}%" if stock.perf_ytd else "N/A"
        return f"Price: {price} | YTD: {ytd} | Sector: {stock.sector or 'Unknown'}"

    elif strategy_name == "Value Stocks":
        pe = f"{stock.price_earnings_ttm:.2f}" if stock.price_earnings_ttm else "N/A"
        return f"Price: {price} | P/E: {pe} | Sector: {stock.sector or 'Unknown'}"

    elif strategy_name == "Dividend Champions":
        div_yield = f"{stock.dividend_yield_recent:.2f}%" if stock.dividend_yield_recent else "N/A"
        return f"Price: {price} | Dividend Yield: {div_yield} | Sector: {stock.sector or 'Unknown'}"

    elif strategy_name == "Market Giants":
        market_cap = f"${stock.market_cap_basic:,.0f}M" if stock.market_cap_basic else "N/A"
        return f"Price: {price} | Market Cap: {market_cap} | Sector: {stock.sector or 'Unknown'}"

    return f"Price: {price} | Sector: {stock.sector or 'Unknown'}"

# Run the advanced screening
asyncio.run(advanced_stock_screening())
```

## API Reference Summary

### Class: ScannerService
- `__init__(base_url, timeout, max_retries, user_agent)`: Initialize service
- `scan_market(market, request, label_product)`: Scan specific market
- `scan_market_by_id(market_id, request, label_product)`: Scan market by string ID
- `__aenter__()` / `__aexit__()`: Async context manager support

### Helper Functions
- `create_comprehensive_request(sort_by, sort_order, range_start, range_end, language)`: Create comprehensive scanner request

### Exception Classes
- `ScannerServiceError`: Base exception
- `ScannerConnectionError`: Connection failures
- `ScannerAPIError`: API response errors
- `ScannerValidationError`: Response validation failures

### Configuration Options
- **Base URL**: Default "https://scanner.tradingview.com"
- **Timeout**: Default 30.0 seconds
- **Max Retries**: Default 3 attempts
- **Retry Strategy**: Exponential backoff (2^attempt seconds)

## Related Components

**Core Dependencies**:
- `httpx`: Async HTTP client for API requests
- `asyncio`: Async programming support
- `json`: JSON response parsing
- `pydantic`: Response validation and type safety

**Integration Points**:
- **Market Models**: Uses Market enum and market validation
- **Scanner Models**: ScannerRequest, ScannerResponse, ColumnSets
- **Data Export**: Compatible with DataExporter for multi-format output
- **Error Handling**: Comprehensive exception hierarchy for robust applications

---

**Note**: This documentation reflects tvkit v0.1.4. The ScannerService provides the core functionality for accessing TradingView's market screening capabilities across 69+ global markets with 101+ financial metrics.