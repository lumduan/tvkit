# Scanner Service Methods

This document provides comprehensive usage documentation for all public methods in the Scanner Service module.

**Module**: `tvkit.api.scanner.services.scanner_service.py`

The Scanner Service provides methods for interacting with TradingView's scanner API to retrieve market data and stock information with comprehensive filtering and sorting capabilities.

## Table of Contents

- [Constructor](#constructor)
- [Market Scanning Methods](#market-scanning-methods)
- [Utility Functions](#utility-functions)
- [Error Handling](#error-handling)
- [Configuration Examples](#configuration-examples)

---

## Constructor

### `__init__()`

```python
def __init__(
    self,
    base_url: str = "https://scanner.tradingview.com",
    timeout: float = 30.0,
    max_retries: int = 3,
    user_agent: str = "tvkit/1.0",
) -> None
```

Initialize the scanner service with configuration parameters for API communication.

#### Parameters
- `base_url` (str, optional): Base URL for the scanner API (default: "https://scanner.tradingview.com")
- `timeout` (float, optional): Request timeout in seconds (default: 30.0)
- `max_retries` (int, optional): Maximum number of retry attempts (default: 3)
- `user_agent` (str, optional): User agent string for requests (default: "tvkit/1.0")

#### Returns
- None

#### Example
```python
from tvkit.api.scanner.services import ScannerService

# Use default settings
service = ScannerService()

# Custom configuration
service = ScannerService(
    timeout=60.0, 
    max_retries=5,
    user_agent="MyApp/2.0"
)
```

---

## Market Scanning Methods

### `scan_market()`

```python
async def scan_market(
    self,
    market: Market,
    request: ScannerRequest,
    label_product: str = "markets-screener",
) -> ScannerResponse
```

Scan a specific market using the scanner API with Market enum for type safety.

#### Parameters
- `market` (Market): Market to scan (use Market enum from `tvkit.api.scanner.markets`)
- `request` (ScannerRequest): Scanner request configuration with columns, filters, and sorting
- `label_product` (str, optional): Label product parameter for the API (default: "markets-screener")

#### Returns
- `ScannerResponse`: Parsed scanner response with stock data and metadata

#### Raises
- `ScannerConnectionError`: If connection fails after retries
- `ScannerAPIError`: If API returns an error response
- `ScannerValidationError`: If response validation fails
- `ValueError`: If market is invalid

#### Example
```python
from tvkit.api.scanner.models import create_scanner_request, ColumnSets
from tvkit.api.scanner.markets import Market
from tvkit.api.scanner.services import ScannerService

async def scan_thai_market():
    service = ScannerService()
    request = create_scanner_request(
        columns=ColumnSets.BASIC,
        range_end=50
    )
    
    response = await service.scan_market(Market.THAILAND, request)
    print(f"Found {len(response.data)} stocks")
    
    for stock in response.data[:5]:  # Show first 5 stocks
        print(f"Stock: {stock.name}, Market Cap: {stock.market_cap_basic}")
        
    return response

# Usage
response = await scan_thai_market()
```

#### Example Output
```python
Found 50 stocks
Stock: AOT, Market Cap: 125000000000
Stock: CPALL, Market Cap: 850000000000
Stock: PTT, Market Cap: 520000000000
Stock: KBANK, Market Cap: 780000000000
Stock: SCB, Market Cap: 650000000000

ScannerResponse(
    data=[
        StockData(name="AOT", market_cap_basic=125000000000, close=65.50, volume=2500000),
        StockData(name="CPALL", market_cap_basic=850000000000, close=58.25, volume=1800000),
        StockData(name="PTT", market_cap_basic=520000000000, close=35.75, volume=3200000),
        # ... 47 more stocks
    ],
    total_count=50,
    columns=["name", "market_cap_basic", "close", "volume"]
)
```

---

### `scan_market_by_id()`

```python
async def scan_market_by_id(
    self,
    market_id: str,
    request: ScannerRequest,
    label_product: str = "markets-screener",
) -> ScannerResponse
```

Scan a specific market using market identifier string for dynamic market selection.

#### Parameters
- `market_id` (str): Market identifier string (e.g., 'thailand', 'america', 'japan', 'germany')
- `request` (ScannerRequest): Scanner request configuration
- `label_product` (str, optional): Label product parameter for the API (default: "markets-screener")

#### Returns
- `ScannerResponse`: Parsed scanner response with stock data

#### Raises
- `ScannerConnectionError`: If connection fails after retries
- `ScannerAPIError`: If API returns an error response
- `ScannerValidationError`: If response validation fails
- `ValueError`: If market_id is invalid

#### Example
```python
from tvkit.api.scanner.services import ScannerService, create_comprehensive_request

async def scan_multiple_markets():
    service = ScannerService()
    markets = ["thailand", "america", "japan"]
    results = {}
    
    for market_id in markets:
        try:
            request = create_comprehensive_request(range_end=20)
            response = await service.scan_market_by_id(market_id, request)
            results[market_id] = response
            print(f"{market_id.upper()}: {len(response.data)} stocks retrieved")
        except ValueError as e:
            print(f"Invalid market {market_id}: {e}")
    
    return results

# Usage
results = await scan_multiple_markets()
```

#### Example Output
```python
THAILAND: 20 stocks retrieved
AMERICA: 20 stocks retrieved  
JAPAN: 20 stocks retrieved

{
    "thailand": ScannerResponse(
        data=[
            StockData(
                name="AOT",
                market_cap_basic=125000000000,
                close=65.50,
                volume=2500000,
                pe_ratio=18.5,
                dividend_yield=0.045,
                revenue_growth=0.12
            ),
            # ... more Thai stocks with comprehensive data
        ],
        total_count=20
    ),
    "america": ScannerResponse(data=[...], total_count=20),
    "japan": ScannerResponse(data=[...], total_count=20)
}
```

---

## Utility Functions

### `create_comprehensive_request()`

```python
def create_comprehensive_request(
    sort_by: str = "name",
    sort_order: Literal["asc", "desc"] = "asc",
    range_start: int = 0,
    range_end: int = 1000,
    language: str = "en",
) -> ScannerRequest
```

Create a comprehensive scanner request with all available columns for maximum data coverage. This function uses the complete set of TradingView scanner columns (101+ fields).

#### Parameters
- `sort_by` (str, optional): Field to sort by (e.g., 'name', 'market_cap_basic', 'volume', 'pe_ratio') (default: "name")
- `sort_order` (Literal["asc", "desc"], optional): Sort order ascending or descending (default: "asc")
- `range_start` (int, optional): Start index for results (0-based) (default: 0)
- `range_end` (int, optional): End index for results (exclusive) (default: 1000)
- `language` (str, optional): Language code for response localization (default: "en")

#### Returns
- `ScannerRequest`: Configured ScannerRequest with comprehensive column set

#### Raises
- `ValueError`: If range parameters are invalid (e.g., range_start >= range_end)

#### Example
```python
from tvkit.api.scanner.services import create_comprehensive_request, ScannerService
from tvkit.api.scanner.markets import Market

async def get_top_stocks_by_market_cap():
    # Create request for top 50 stocks by market cap
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=50
    )
    
    service = ScannerService()
    response = await service.scan_market(Market.AMERICA, request)
    
    print(f"Top 50 US stocks by market cap:")
    for i, stock in enumerate(response.data[:10], 1):
        market_cap_billions = stock.market_cap_basic / 1_000_000_000
        print(f"{i:2d}. {stock.name:8s} - ${market_cap_billions:,.1f}B")
    
    return response

# Usage
response = await get_top_stocks_by_market_cap()
```

#### Example Output
```python
Top 50 US stocks by market cap:
 1. AAPL     - $2,850.5B
 2. MSFT     - $2,720.8B
 3. GOOGL    - $1,680.2B
 4. AMZN     - $1,520.9B
 5. NVDA     - $1,450.3B
 6. TSLA     - $850.7B
 7. META     - $720.4B
 8. BRK.A    - $680.1B
 9. V        - $520.8B
10. JNJ      - $450.2B

ScannerRequest(
    columns=[
        "name", "market_cap_basic", "close", "volume", "pe_ratio", "dividend_yield", 
        "revenue_growth", "debt_to_equity", "roa", "roe", "current_ratio", "quick_ratio", 
        "gross_margin", "operating_margin", "net_margin", "asset_turnover", "inventory_turnover",
        "receivables_turnover", "total_debt", "total_revenue", "ebitda", "free_cash_flow",
        # ... 88+ more columns for comprehensive financial analysis
    ],
    sort=SortConfig(sortBy="market_cap_basic", sortOrder="desc", nullsFirst=False),
    range=(0, 50),
    preset="all_stocks",
    options=ScannerOptions(lang="en")
)
```

---

## Error Handling

### Exception Hierarchy

The Scanner Service uses a structured exception hierarchy for clear error handling:

```python
ScannerServiceError (base)
├── ScannerConnectionError    # Network/connection issues
├── ScannerAPIError          # API response errors (4xx, 5xx)
└── ScannerValidationError   # Response parsing/validation errors
```

### Retry Logic

The service implements exponential backoff retry logic:
- **Retryable errors**: Connection timeouts, network errors
- **Non-retryable errors**: API errors (4xx), validation errors
- **Backoff formula**: `2^attempt` seconds (1s, 2s, 4s, etc.)

#### Example with Error Handling

```python
from tvkit.api.scanner.services import (
    ScannerService, 
    ScannerConnectionError, 
    ScannerAPIError, 
    ScannerValidationError
)
from tvkit.api.scanner.models import create_scanner_request, ColumnSets
from tvkit.api.scanner.markets import Market

async def robust_market_scan():
    service = ScannerService(max_retries=5, timeout=60.0)
    
    try:
        request = create_scanner_request(
            columns=ColumnSets.FUNDAMENTALS,
            range_end=100
        )
        
        response = await service.scan_market(Market.AMERICA, request)
        print(f"✅ Successfully retrieved {len(response.data)} stocks")
        return response
        
    except ScannerConnectionError as e:
        print(f"❌ Connection failed after retries: {e}")
        
    except ScannerAPIError as e:
        print(f"❌ API error (check request parameters): {e}")
        
    except ScannerValidationError as e:
        print(f"❌ Response validation failed: {e}")
        
    except ValueError as e:
        print(f"❌ Invalid parameters: {e}")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    return None

# Usage with error handling
response = await robust_market_scan()
```

### Async Context Management

The Scanner Service supports async context managers for resource management:

```python
async with ScannerService() as service:
    # HTTP client resources automatically managed
    response = await service.scan_market(Market.THAILAND, request)
    # Resources automatically cleaned up when exiting context
```

---

## Configuration Examples

### Basic Market Screening

```python
from tvkit.api.scanner.models import create_scanner_request, ColumnSets
from tvkit.api.scanner.markets import Market
from tvkit.api.scanner.services import ScannerService

async def basic_screening():
    service = ScannerService()
    
    # Basic stock information
    request = create_scanner_request(
        columns=ColumnSets.BASIC,
        range_end=20
    )
    
    response = await service.scan_market(Market.THAILAND, request)
    return response
```

### Advanced Fundamental Analysis

```python
async def fundamental_analysis():
    service = ScannerService()
    
    # Comprehensive fundamental data
    request = create_comprehensive_request(
        sort_by="pe_ratio",
        sort_order="asc",  # Low P/E first
        range_end=50
    )
    
    response = await service.scan_market(Market.AMERICA, request)
    
    # Filter for value stocks
    value_stocks = [
        stock for stock in response.data 
        if hasattr(stock, 'pe_ratio') and stock.pe_ratio is not None 
        and stock.pe_ratio < 15  # P/E ratio less than 15
    ]
    
    print(f"Found {len(value_stocks)} value stocks with P/E < 15")
    return value_stocks
```

### Multi-Market Comparison

```python
async def multi_market_comparison():
    service = ScannerService()
    markets = ["america", "europe", "asia"]
    
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=10  # Top 10 from each market
    )
    
    results = {}
    for market_id in markets:
        try:
            response = await service.scan_market_by_id(market_id, request)
            results[market_id] = response.data
            
            avg_market_cap = sum(
                stock.market_cap_basic or 0 for stock in response.data
            ) / len(response.data)
            
            print(f"{market_id.upper()}: Avg Market Cap = ${avg_market_cap/1e9:.1f}B")
            
        except Exception as e:
            print(f"Error scanning {market_id}: {e}")
    
    return results
```

### Performance Monitoring

```python
import time
from typing import Dict, Any

async def performance_monitoring():
    service = ScannerService()
    
    metrics: Dict[str, Any] = {
        "requests": 0,
        "total_time": 0,
        "errors": 0
    }
    
    markets = ["thailand", "singapore", "malaysia"]
    
    for market_id in markets:
        start_time = time.time()
        
        try:
            request = create_comprehensive_request(range_end=50)
            response = await service.scan_market_by_id(market_id, request)
            
            metrics["requests"] += 1
            metrics["total_time"] += time.time() - start_time
            
            print(f"✅ {market_id}: {len(response.data)} stocks in {time.time() - start_time:.2f}s")
            
        except Exception as e:
            metrics["errors"] += 1
            print(f"❌ {market_id}: Error - {e}")
    
    avg_time = metrics["total_time"] / max(metrics["requests"], 1)
    print(f"\nPerformance Summary:")
    print(f"  Successful requests: {metrics['requests']}")
    print(f"  Average response time: {avg_time:.2f}s")
    print(f"  Error rate: {metrics['errors'] / (metrics['requests'] + metrics['errors']) * 100:.1f}%")
    
    return metrics
```

These examples demonstrate the flexibility and power of the Scanner Service for various market analysis scenarios, from basic screening to comprehensive multi-market analysis.