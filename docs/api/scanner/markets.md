# Markets Module Documentation

## Overview

The `markets` module provides comprehensive market identifiers, metadata, and geographical organization for TradingView's scanner API. It defines 69+ global markets across 6 regions with detailed exchange information, enabling systematic stock screening and market analysis worldwide.

**Module Path**: `tvkit.api.scanner.markets`

## Architecture

The markets module serves as the foundational reference for global market coverage:

- **Market Enumeration**: Type-safe market identifiers extracted from TradingView's official data
- **Exchange Mapping**: Detailed exchange information for each market
- **Regional Organization**: Logical grouping of markets by geographical regions
- **Metadata Integration**: Rich market information including names, descriptions, and exchange lists
- **Validation Functions**: Utilities for market identifier validation and discovery
- **Global Coverage**: 69+ markets spanning all major financial centers worldwide

## Data Structures

### MarketInfo

```python
class MarketInfo(NamedTuple):
    """Market information containing display name and exchanges."""

    name: str
    exchanges: List[str]
    description: str
```

**Description**: Immutable data structure containing comprehensive market metadata.

**Fields**:
- `name` (str): Human-readable market name (e.g., "Thailand", "United States")
- `exchanges` (List[str]): List of exchange identifiers for the market
- `description` (str): Detailed market description

**Usage Example**:
```python
from tvkit.api.scanner.markets import get_market_info, Market

info = get_market_info(Market.THAILAND)
print(f"Market: {info.name}")           # "Thailand"
print(f"Exchanges: {info.exchanges}")   # ["SET"]
print(f"Description: {info.description}") # "Thai stock market"
```

### Market Enum

```python
class Market(str, Enum):
    """
    Available markets for TradingView scanner API.

    Values correspond to the market identifiers used in scanner API endpoints.
    """
```

**Description**: String-based enumeration of all supported markets with TradingView-compatible identifiers.

**Design Features**:
- **String Inheritance**: Direct string values for API compatibility
- **Type Safety**: Enum validation prevents invalid market usage
- **IDE Support**: Auto-completion and type checking
- **API Compatibility**: Values match TradingView's internal identifiers

## Market Coverage

### Global Markets (69+ Markets)

#### North America (2 Markets)
```python
Market.AMERICA     # USA - NASDAQ, NYSE, NYSE ARCA, OTC
Market.CANADA      # Canada - TSX, TSXV, CSE, NEO
```

**Major Exchanges**:
- **USA**: NASDAQ (tech-heavy), NYSE (blue-chip), NYSE ARCA (ETFs), OTC (small caps)
- **Canada**: TSX (large caps), TSXV (growth companies), CSE (emerging), NEO (innovation)

#### Europe (30 Markets)
```python
# Western Europe
Market.UK          # United Kingdom - LSE, LSIN, AQUIS
Market.GERMANY     # Germany - FWB, XETR, TRADEGATE + 9 regional
Market.FRANCE      # France - EURONEXTPAR
Market.NETHERLANDS # Netherlands - EURONEXTAMS
Market.SWITZERLAND # Switzerland - SIX, BX
Market.ITALY       # Italy - MIL, EUROTLX
Market.SPAIN       # Spain - BME
Market.BELGIUM     # Belgium - EURONEXTBRU

# Nordic Countries
Market.SWEDEN      # Sweden - NGM, OMXSTO
Market.NORWAY      # Norway - EURONEXTOSE
Market.DENMARK     # Denmark - OMXCOP
Market.FINLAND     # Finland - OMXHEX
Market.ICELAND     # Iceland - OMXICE

# Eastern Europe
Market.POLAND      # Poland - GPW, NEWCONNECT
Market.RUSSIA      # Russia - RUS
Market.CZECH       # Czech Republic - PSECZ
Market.HUNGARY     # Hungary - BET
Market.ROMANIA     # Romania - BVB
Market.SLOVAKIA    # Slovakia - BSSE

# Baltic States
Market.ESTONIA     # Estonia - OMXTSE
Market.LITHUANIA   # Lithuania - OMXVSE
Market.LATVIA      # Latvia - OMXRSE

# Others
Market.TURKEY      # Turkey - BIST
Market.AUSTRIA     # Austria - VIE
Market.PORTUGAL    # Portugal - EURONEXTLIS
Market.IRELAND     # Ireland - EURONEXTDUB
Market.GREECE      # Greece - ATHEX
Market.CYPRUS      # Cyprus - CSECY
Market.LUXEMBOURG  # Luxembourg - LUXSE
Market.SERBIA      # Serbia - BELEX
```

#### Asia Pacific (16 Markets)
```python
# East Asia
Market.JAPAN       # Japan - TSE, NAG, FSE, SAPSE
Market.KOREA       # South Korea - KRX
Market.CHINA       # Mainland China - SSE, SZSE, SHFE, ZCE, CFFEX
Market.HONGKONG    # Hong Kong - HKEX
Market.TAIWAN      # Taiwan - TWSE, TPEX

# Southeast Asia
Market.THAILAND    # Thailand - SET
Market.SINGAPORE   # Singapore - SGX
Market.MALAYSIA    # Malaysia - MYX
Market.INDONESIA   # Indonesia - IDX
Market.PHILIPPINES # Philippines - PSE
Market.VIETNAM     # Vietnam - HOSE, HNX, UPCOM

# South Asia
Market.INDIA       # India - BSE, NSE
Market.PAKISTAN    # Pakistan - PSX
Market.BANGLADESH  # Bangladesh - DSEBD
Market.SRILANKA    # Sri Lanka - CSELK

# Oceania
Market.AUSTRALIA   # Australia - ASX
Market.NEWZEALAND  # New Zealand - NZX
```

#### Middle East & Africa (12 Markets)
```python
# Middle East
Market.UAE         # United Arab Emirates - DFM, ADX, NASDAQDUBAI
Market.KSA         # Saudi Arabia - TADAWUL
Market.ISRAEL      # Israel - TASE
Market.QATAR       # Qatar - QSE
Market.KUWAIT      # Kuwait - KSE
Market.BAHRAIN     # Bahrain - BAHRAIN

# Africa
Market.RSA         # South Africa - JSE
Market.EGYPT       # Egypt - EGX
Market.MOROCCO     # Morocco - CSEMA
Market.TUNISIA     # Tunisia - BVMT
Market.KENYA       # Kenya - NSEKE
Market.NIGERIA     # Nigeria - NSENG
```

#### Latin America (7 Markets)
```python
Market.BRAZIL      # Brazil - BMFBOVESPA
Market.MEXICO      # Mexico - BMV, BIVA
Market.ARGENTINA   # Argentina - BYMA, BCBA
Market.CHILE       # Chile - BCS
Market.COLOMBIA    # Colombia - BVC
Market.PERU        # Peru - BVL
Market.VENEZUELA   # Venezuela - BVCV
```

#### Global Overview
```python
Market.GLOBAL      # Entire world - Global markets overview
```

### MarketRegion Enum

```python
class MarketRegion(str, Enum):
    """Market regions for grouping markets."""

    GLOBAL = "global"
    NORTH_AMERICA = "north_america"
    EUROPE = "europe"
    MIDDLE_EAST_AFRICA = "middle_east_africa"
    MEXICO_SOUTH_AMERICA = "mexico_south_america"
    ASIA_PACIFIC = "asia_pacific"
```

**Regional Distribution**:
- **North America**: 2 markets (USA, Canada)
- **Europe**: 30 markets (covering Western, Eastern, Nordic, and Baltic regions)
- **Asia Pacific**: 16 markets (East Asia, Southeast Asia, South Asia, Oceania)
- **Middle East & Africa**: 12 markets (Gulf states, Levant, North/Sub-Saharan Africa)
- **Latin America**: 7 markets (South America, Central America, Mexico)
- **Global**: 1 market (worldwide overview)

## Core Functions

### Market Information Retrieval

#### get_market_info()

```python
def get_market_info(market: Market) -> MarketInfo
```

**Description**: Retrieves comprehensive metadata for a specified market.

**Parameters**:
- `market` (Market): Market enum value to get information for

**Returns**: `MarketInfo` object containing:
- Market display name
- List of associated exchanges
- Market description

**Usage Examples**:
```python
from tvkit.api.scanner.markets import get_market_info, Market

# Get Thai market information
thai_info = get_market_info(Market.THAILAND)
print(f"Name: {thai_info.name}")         # "Thailand"
print(f"Exchanges: {thai_info.exchanges}") # ["SET"]
print(f"Description: {thai_info.description}") # "Thai stock market"

# Get US market information
us_info = get_market_info(Market.AMERICA)
print(f"Name: {us_info.name}")           # "USA"
print(f"Exchanges: {us_info.exchanges}") # ["NASDAQ", "NYSE", "NYSE ARCA", "OTC"]

# Get German market information
german_info = get_market_info(Market.GERMANY)
print(f"Exchanges: {len(german_info.exchanges)} exchanges") # 12 exchanges
```

### Regional Market Discovery

#### get_markets_by_region()

```python
def get_markets_by_region(region: MarketRegion) -> List[Market]
```

**Description**: Returns all markets within a specified geographical region.

**Parameters**:
- `region` (MarketRegion): Regional classification to filter markets

**Returns**: List of Market enum values in the specified region

**Regional Coverage**:
- **NORTH_AMERICA**: USA, Canada (2 markets)
- **EUROPE**: All European markets including Nordic and Eastern Europe (30 markets)
- **ASIA_PACIFIC**: East Asia, Southeast Asia, South Asia, Oceania (16 markets)
- **MIDDLE_EAST_AFRICA**: Gulf, Levant, African markets (12 markets)
- **MEXICO_SOUTH_AMERICA**: Latin American markets (7 markets)

**Usage Examples**:
```python
from tvkit.api.scanner.markets import get_markets_by_region, MarketRegion

# Get all Asian markets
asia_markets = get_markets_by_region(MarketRegion.ASIA_PACIFIC)
print(f"Asia Pacific markets: {len(asia_markets)}")  # 16 markets

for market in asia_markets[:5]:  # Show first 5
    info = get_market_info(market)
    print(f"- {info.name}: {market.value}")

# Get European markets
europe_markets = get_markets_by_region(MarketRegion.EUROPE)
print(f"European markets: {len(europe_markets)}")   # 30 markets

# Get North American markets
na_markets = get_markets_by_region(MarketRegion.NORTH_AMERICA)
print(f"North American markets: {[m.value for m in na_markets]}")
# ['america', 'canada']
```

### Market Discovery and Validation

#### get_all_markets()

```python
def get_all_markets() -> List[Market]
```

**Description**: Returns complete list of all available markets across all regions.

**Returns**: List containing all 69+ Market enum values

**Usage Examples**:
```python
from tvkit.api.scanner.markets import get_all_markets

# Get complete market list
all_markets = get_all_markets()
print(f"Total markets available: {len(all_markets)}")  # 69+ markets

# Analyze market distribution by region
from collections import defaultdict

region_distribution = defaultdict(int)
for market in all_markets:
    for region, markets in MARKETS_BY_REGION.items():
        if market in markets:
            region_distribution[region.value] += 1

for region, count in region_distribution.items():
    print(f"{region.replace('_', ' ').title()}: {count} markets")
```

#### is_valid_market()

```python
def is_valid_market(market_id: str) -> bool
```

**Description**: Validates whether a string identifier corresponds to a valid market.

**Parameters**:
- `market_id` (str): Market identifier string to validate

**Returns**: `True` if valid market identifier, `False` otherwise

**Validation Logic**:
- Attempts to create Market enum from string
- Returns `False` for invalid identifiers without raising exceptions
- Case-sensitive validation matching TradingView identifiers

**Usage Examples**:
```python
from tvkit.api.scanner.markets import is_valid_market

# Valid market identifiers
print(is_valid_market("thailand"))    # True
print(is_valid_market("america"))     # True
print(is_valid_market("germany"))     # True

# Invalid identifiers
print(is_valid_market("invalid"))     # False
print(is_valid_market("THAILAND"))    # False (case-sensitive)
print(is_valid_market(""))           # False

# Use in validation workflow
def safe_market_lookup(market_id: str):
    if is_valid_market(market_id):
        return Market(market_id)
    else:
        raise ValueError(f"Invalid market identifier: {market_id}")

# Usage
try:
    market = safe_market_lookup("thailand")
    print(f"Valid market: {market.value}")
except ValueError as e:
    print(f"Error: {e}")
```

## Market Metadata Reference

### Exchange Information by Market

#### North America
```python
# USA (Market.AMERICA)
exchanges = ["NASDAQ", "NYSE", "NYSE ARCA", "OTC"]
# NASDAQ: Technology-focused exchange
# NYSE: Traditional blue-chip exchange
# NYSE ARCA: ETF and options trading
# OTC: Over-the-counter small caps

# Canada (Market.CANADA)
exchanges = ["TSX", "TSXV", "CSE", "NEO"]
# TSX: Toronto Stock Exchange (large caps)
# TSXV: TSX Venture Exchange (growth companies)
# CSE: Canadian Securities Exchange (emerging)
# NEO: NEO Exchange (innovation-focused)
```

#### Major European Markets
```python
# Germany (Market.GERMANY) - 12 Exchanges
exchanges = [
    "FWB",        # Frankfurt Stock Exchange (main)
    "XETR",       # Xetra (electronic trading)
    "TRADEGATE",  # Tradegate Exchange
    "SWB", "BER", "DUS", "HAM", "HAN", "MUN",  # Regional exchanges
    "LS", "LSX", "GETTEX"  # Electronic platforms
]

# United Kingdom (Market.UK)
exchanges = ["LSE", "LSIN", "AQUIS"]
# LSE: London Stock Exchange
# LSIN: London Stock Exchange International
# AQUIS: Alternative trading system

# France (Market.FRANCE)
exchanges = ["EURONEXTPAR"]  # Euronext Paris

# Netherlands (Market.NETHERLANDS)
exchanges = ["EURONEXTAMS"]  # Euronext Amsterdam
```

#### Major Asian Markets
```python
# Japan (Market.JAPAN)
exchanges = ["TSE", "NAG", "FSE", "SAPSE"]
# TSE: Tokyo Stock Exchange
# NAG: Nagoya Stock Exchange
# FSE: Fukuoka Stock Exchange
# SAPSE: Sapporo Securities Exchange

# China (Market.CHINA)
exchanges = ["SSE", "SZSE", "SHFE", "ZCE", "CFFEX"]
# SSE: Shanghai Stock Exchange
# SZSE: Shenzhen Stock Exchange
# SHFE: Shanghai Futures Exchange
# ZCE: Zhengzhou Commodity Exchange
# CFFEX: China Financial Futures Exchange

# India (Market.INDIA)
exchanges = ["BSE", "NSE"]
# BSE: Bombay Stock Exchange
# NSE: National Stock Exchange of India
```

### Market Descriptions

All markets include descriptive metadata:

```python
examples = {
    Market.THAILAND: "Thai stock market",
    Market.AMERICA: "United States stock markets",
    Market.GERMANY: "German stock markets",
    Market.JAPAN: "Japanese stock markets",
    Market.BRAZIL: "Brazilian stock market",
    Market.UAE: "UAE stock markets",
    Market.AUSTRALIA: "Australian stock market"
}
```

## Usage Patterns and Examples

### Regional Market Analysis

```python
async def analyze_markets_by_region():
    """Analyze market coverage and characteristics by region"""

    from tvkit.api.scanner.markets import (
        MarketRegion, get_markets_by_region, get_market_info
    )

    print("📊 Global Market Coverage Analysis")
    print("=" * 50)

    regional_analysis = {}

    for region in MarketRegion:
        if region == MarketRegion.GLOBAL:
            continue  # Skip global overview

        markets = get_markets_by_region(region)
        region_name = region.value.replace('_', ' ').title()

        print(f"\n🌍 {region_name} ({len(markets)} markets)")
        print("-" * 40)

        # Analyze exchanges per market
        exchange_counts = []
        total_exchanges = 0

        for market in markets[:10]:  # Show first 10 for brevity
            info = get_market_info(market)
            exchange_count = len(info.exchanges)
            exchange_counts.append(exchange_count)
            total_exchanges += exchange_count

            # Format exchange list
            exchange_list = ", ".join(info.exchanges[:3])  # First 3 exchanges
            if len(info.exchanges) > 3:
                exchange_list += f" (+{len(info.exchanges)-3} more)"

            print(f"  • {info.name:<20} | {exchange_count:2d} exchanges | {exchange_list}")

        if len(markets) > 10:
            print(f"  ... and {len(markets)-10} more markets")

        # Regional statistics
        avg_exchanges = total_exchanges / min(len(markets), 10)
        regional_analysis[region_name] = {
            "market_count": len(markets),
            "total_exchanges": total_exchanges,
            "avg_exchanges_per_market": avg_exchanges
        }

        print(f"\n  📈 Regional Summary:")
        print(f"     Markets: {len(markets)}")
        print(f"     Total Exchanges: {total_exchanges}")
        print(f"     Avg Exchanges/Market: {avg_exchanges:.1f}")

    return regional_analysis

# Run analysis
import asyncio
analysis = asyncio.run(analyze_markets_by_region())
```

### Market Discovery and Validation

```python
def market_discovery_toolkit():
    """Comprehensive market discovery and validation toolkit"""

    from tvkit.api.scanner.markets import (
        get_all_markets, get_market_info, is_valid_market,
        get_markets_by_region, MarketRegion, Market
    )

    print("🔍 Market Discovery Toolkit")
    print("=" * 40)

    # 1. Global market overview
    all_markets = get_all_markets()
    print(f"📊 Total Markets Available: {len(all_markets)}")

    # 2. Market validation examples
    print(f"\n✅ Market Validation Examples:")
    test_identifiers = [
        "thailand", "america", "germany", "japan",  # Valid
        "invalid", "THAILAND", "", "fake_market"    # Invalid
    ]

    for identifier in test_identifiers:
        is_valid = is_valid_market(identifier)
        status = "✅ Valid" if is_valid else "❌ Invalid"
        print(f"   '{identifier}': {status}")

    # 3. Market search functionality
    def find_markets_by_name(search_term: str):
        """Find markets containing search term in name"""
        matches = []
        for market in get_all_markets():
            info = get_market_info(market)
            if search_term.lower() in info.name.lower():
                matches.append((market, info))
        return matches

    print(f"\n🔎 Market Search Examples:")
    search_terms = ["United", "China", "Euro"]

    for term in search_terms:
        matches = find_markets_by_name(term)
        print(f"   '{term}': {len(matches)} matches")
        for market, info in matches[:3]:  # Show first 3
            print(f"      • {info.name} ({market.value})")

    # 4. Exchange analysis
    print(f"\n🏛️  Exchange Analysis:")

    # Markets with most exchanges
    market_exchange_counts = []
    for market in all_markets:
        info = get_market_info(market)
        market_exchange_counts.append((market, info, len(info.exchanges)))

    # Sort by exchange count
    market_exchange_counts.sort(key=lambda x: x[2], reverse=True)

    print(f"   Top 5 Markets by Exchange Count:")
    for market, info, count in market_exchange_counts[:5]:
        print(f"      {info.name}: {count} exchanges ({', '.join(info.exchanges[:2])}...)")

    # 5. Regional distribution
    print(f"\n🌍 Regional Distribution:")
    for region in MarketRegion:
        if region == MarketRegion.GLOBAL:
            continue
        markets = get_markets_by_region(region)
        region_name = region.value.replace('_', ' ').title()
        print(f"   {region_name}: {len(markets)} markets")

# Run toolkit
market_discovery_toolkit()
```

### Integration with Scanner Service

```python
async def comprehensive_market_screening():
    """Demonstrate integration between markets and scanner service"""

    from tvkit.api.scanner.services import ScannerService, create_comprehensive_request
    from tvkit.api.scanner.markets import (
        get_markets_by_region, MarketRegion, get_market_info
    )

    service = ScannerService()

    # Screen top markets from each region
    regional_screening_results = {}

    # Select representative markets from each region
    target_markets_by_region = {
        MarketRegion.NORTH_AMERICA: [Market.AMERICA],
        MarketRegion.EUROPE: [Market.UK, Market.GERMANY],
        MarketRegion.ASIA_PACIFIC: [Market.JAPAN, Market.THAILAND],
        MarketRegion.MIDDLE_EAST_AFRICA: [Market.UAE, Market.RSA],
        MarketRegion.MEXICO_SOUTH_AMERICA: [Market.BRAZIL]
    }

    # Create screening request for top companies by market cap
    request = create_comprehensive_request(
        sort_by="market_cap_basic",
        sort_order="desc",
        range_end=10  # Top 10 companies per market
    )

    print("🌐 Global Market Screening - Top 10 Companies by Market Cap")
    print("=" * 70)

    for region, markets in target_markets_by_region.items():
        region_name = region.value.replace('_', ' ').title()
        print(f"\n📍 {region_name}")
        print("-" * 40)

        region_results = {}

        for market in markets:
            try:
                info = get_market_info(market)
                print(f"\n🏛️  {info.name} ({market.value})")

                response = await service.scan_market(market, request)
                stocks = response.data

                if stocks:
                    print(f"   ✅ Found {len(stocks)} companies")

                    # Show top 3 companies
                    for i, stock in enumerate(stocks[:3], 1):
                        market_cap = f"${stock.market_cap_basic:,.0f}M" if stock.market_cap_basic else "N/A"
                        print(f"   {i}. {stock.name}")
                        print(f"      Market Cap: {market_cap} | Price: ${stock.close:.2f}")

                    # Market statistics
                    total_market_cap = sum(s.market_cap_basic or 0 for s in stocks)
                    region_results[market.value] = {
                        "companies": len(stocks),
                        "largest_company": stocks[0].name,
                        "total_top10_market_cap": total_market_cap,
                        "exchanges": info.exchanges
                    }

                    print(f"   📊 Top 10 Combined Market Cap: ${total_market_cap:,.0f}M")
                    print(f"   🏛️  Exchanges: {', '.join(info.exchanges)}")
                else:
                    region_results[market.value] = {"error": "No data"}
                    print(f"   ❌ No data available")

            except Exception as e:
                region_results[market.value] = {"error": str(e)}
                print(f"   ❌ Error: {e}")

        regional_screening_results[region_name] = region_results

    # Global summary
    print(f"\n🏆 Global Market Leaders:")
    print("=" * 40)

    all_market_leaders = []
    for region_results in regional_screening_results.values():
        for market_data in region_results.values():
            if "largest_company" in market_data:
                all_market_leaders.append({
                    "company": market_data["largest_company"],
                    "market_cap": market_data["total_top10_market_cap"]
                })

    # Sort by market cap and show top companies
    all_market_leaders.sort(key=lambda x: x["market_cap"], reverse=True)

    for i, leader in enumerate(all_market_leaders[:5], 1):
        print(f"{i}. {leader['company']}: ${leader['market_cap']:,.0f}M")

    return regional_screening_results

# Run comprehensive screening
# results = asyncio.run(comprehensive_market_screening())
```

### Market Configuration and Utilities

```python
class MarketConfigurationManager:
    """Advanced market configuration and utilities"""

    def __init__(self):
        self.preferred_markets = []
        self.excluded_markets = []

    def add_preferred_region(self, region: MarketRegion):
        """Add all markets from a region to preferred list"""
        markets = get_markets_by_region(region)
        self.preferred_markets.extend(markets)
        return len(markets)

    def add_preferred_market(self, market: Market):
        """Add specific market to preferred list"""
        if market not in self.preferred_markets:
            self.preferred_markets.append(market)

    def exclude_market(self, market: Market):
        """Exclude market from operations"""
        if market not in self.excluded_markets:
            self.excluded_markets.append(market)
        if market in self.preferred_markets:
            self.preferred_markets.remove(market)

    def get_active_markets(self) -> List[Market]:
        """Get markets that are preferred and not excluded"""
        if not self.preferred_markets:
            # If no preferences, use all markets except excluded
            all_markets = get_all_markets()
            return [m for m in all_markets if m not in self.excluded_markets]

        return [m for m in self.preferred_markets if m not in self.excluded_markets]

    def get_markets_by_exchange_count(self, min_exchanges: int = 1) -> List[Market]:
        """Filter markets by minimum number of exchanges"""
        active_markets = self.get_active_markets()
        filtered_markets = []

        for market in active_markets:
            info = get_market_info(market)
            if len(info.exchanges) >= min_exchanges:
                filtered_markets.append(market)

        return filtered_markets

    def get_market_summary(self) -> dict:
        """Get comprehensive summary of market configuration"""
        active_markets = self.get_active_markets()

        summary = {
            "total_markets": len(get_all_markets()),
            "preferred_markets": len(self.preferred_markets),
            "excluded_markets": len(self.excluded_markets),
            "active_markets": len(active_markets),
            "regional_distribution": {},
            "exchange_analysis": {
                "total_exchanges": 0,
                "markets_with_multiple_exchanges": 0,
                "top_exchange_markets": []
            }
        }

        # Regional analysis
        for region in MarketRegion:
            if region == MarketRegion.GLOBAL:
                continue
            region_markets = get_markets_by_region(region)
            active_in_region = [m for m in region_markets if m in active_markets]
            region_name = region.value.replace('_', ' ').title()
            summary["regional_distribution"][region_name] = {
                "total": len(region_markets),
                "active": len(active_in_region)
            }

        # Exchange analysis
        exchange_counts = []
        for market in active_markets:
            info = get_market_info(market)
            exchange_count = len(info.exchanges)
            summary["exchange_analysis"]["total_exchanges"] += exchange_count

            if exchange_count > 1:
                summary["exchange_analysis"]["markets_with_multiple_exchanges"] += 1

            exchange_counts.append((market, info.name, exchange_count))

        # Top markets by exchange count
        exchange_counts.sort(key=lambda x: x[2], reverse=True)
        summary["exchange_analysis"]["top_exchange_markets"] = [
            {"market": market.value, "name": name, "exchanges": count}
            for market, name, count in exchange_counts[:5]
        ]

        return summary

# Usage example
def demonstrate_market_configuration():
    """Demonstrate advanced market configuration"""

    print("⚙️  Market Configuration Manager Demo")
    print("=" * 45)

    # Create configuration manager
    config = MarketConfigurationManager()

    # Add preferred regions
    print("📍 Adding preferred regions...")
    asia_count = config.add_preferred_region(MarketRegion.ASIA_PACIFIC)
    europe_count = config.add_preferred_region(MarketRegion.EUROPE)
    print(f"   Added {asia_count} Asia Pacific markets")
    print(f"   Added {europe_count} European markets")

    # Add specific preferred markets
    config.add_preferred_market(Market.AMERICA)
    config.add_preferred_market(Market.CANADA)
    print("   Added North American markets individually")

    # Exclude some markets
    config.exclude_market(Market.RUSSIA)  # Exclude due to sanctions
    config.exclude_market(Market.VENEZUELA)  # Exclude due to volatility
    print("   Excluded specific markets")

    # Get configuration summary
    summary = config.get_market_summary()

    print(f"\n📊 Configuration Summary:")
    print(f"   Total available markets: {summary['total_markets']}")
    print(f"   Preferred markets: {summary['preferred_markets']}")
    print(f"   Active markets: {summary['active_markets']}")
    print(f"   Excluded markets: {summary['excluded_markets']}")

    print(f"\n🌍 Regional Distribution:")
    for region, data in summary["regional_distribution"].items():
        print(f"   {region}: {data['active']}/{data['total']} active")

    print(f"\n🏛️  Exchange Analysis:")
    print(f"   Total exchanges: {summary['exchange_analysis']['total_exchanges']}")
    print(f"   Multi-exchange markets: {summary['exchange_analysis']['markets_with_multiple_exchanges']}")

    print(f"\n🔝 Top Markets by Exchange Count:")
    for market_info in summary['exchange_analysis']['top_exchange_markets']:
        print(f"   {market_info['name']}: {market_info['exchanges']} exchanges")

    # Demonstrate filtering
    multi_exchange_markets = config.get_markets_by_exchange_count(min_exchanges=2)
    print(f"\n🎯 Markets with 2+ exchanges: {len(multi_exchange_markets)}")

    return config

# Run demonstration
config = demonstrate_market_configuration()
```

## API Reference Summary

### Classes and Data Structures
- `Market(str, Enum)`: Enumeration of 69+ global markets
- `MarketRegion(str, Enum)`: Geographical region classification
- `MarketInfo(NamedTuple)`: Market metadata structure

### Core Functions
- `get_market_info(market: Market) -> MarketInfo`: Get market metadata
- `get_markets_by_region(region: MarketRegion) -> List[Market]`: Get regional markets
- `get_all_markets() -> List[Market]`: Get all available markets
- `is_valid_market(market_id: str) -> bool`: Validate market identifier

### Data Structures
- `MARKET_INFO`: Dictionary mapping markets to metadata
- `MARKETS_BY_REGION`: Dictionary mapping regions to market lists

### Market Coverage
- **Total Markets**: 69+ global markets
- **Regional Coverage**: 6 major regions (North America, Europe, Asia Pacific, Middle East & Africa, Latin America, Global)
- **Exchange Coverage**: 100+ exchanges worldwide
- **Market Types**: Developed and emerging markets

## Related Components

**Core Dependencies**:
- `enum`: Python enumeration support for type-safe market identifiers
- `typing`: Type hints for function signatures and data structures

**Integration Points**:
- **ScannerService**: Uses Market enum for market-specific screening
- **Scanner Models**: Market identifiers used in request/response models
- **Regional Analysis**: MarketRegion used for geographical market grouping
- **Validation**: Market validation integrated throughout scanner API

---

**Note**: This documentation reflects tvkit v0.1.4. Market identifiers are extracted from TradingView's official market selection and correspond exactly to their internal API identifiers. The module provides comprehensive coverage of global financial markets with detailed exchange information for systematic market analysis.