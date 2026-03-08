# Markets Reference

**Module:** `tvkit.api.scanner.markets`
**Introduced in:** v0.2.0

Market identifiers, regional groupings, and metadata used by the TradingView scanner API. These values correspond to the `{market}` segment in the scanner endpoint:

```
https://scanner.tradingview.com/{market}/scan
```

Pass any `Market` value to `ScannerService.scan_market()` or `ScannerService.scan_market_by_id()`.

## Quick Example

```python
import asyncio
from tvkit.api.scanner.markets import Market, MarketRegion, get_markets_by_region
from tvkit.api.scanner.models import create_scanner_request
from tvkit.api.scanner.services import ScannerService

async def main() -> None:
    # Scan a specific market
    request = create_scanner_request(range_end=10)
    async with ScannerService() as service:
        result = await service.scan_market(Market.JAPAN, request)
    print(f"Found {len(result.data)} stocks in Japan")

    # Scan all Asia-Pacific markets
    ap_markets = get_markets_by_region(MarketRegion.ASIA_PACIFIC)
    print(f"{len(ap_markets)} markets in Asia-Pacific")

asyncio.run(main())
```

---

## Import

```python
from tvkit.api.scanner.markets import (
    Market,
    MarketRegion,
    MarketInfo,
    get_market_info,
    get_markets_by_region,
    get_all_markets,
    is_valid_market,
)
```

---

## `Market`

`StrEnum` of all 69 supported market identifiers used by the TradingView scanner endpoint. Each value maps directly to the `{market}` path segment:

```
https://scanner.tradingview.com/{market}/scan
```

For example, `Market.THAILAND` has value `"thailand"`, which resolves to `https://scanner.tradingview.com/thailand/scan`.

```python
class Market(StrEnum): ...
```

Because `Market` is a `StrEnum`, its values compare equal to plain strings:

```python
Market.AMERICA == "america"  # True
```

### Regional Breakdown

| Region | Count | Markets |
|--------|-------|---------|
| Global | 1 | `GLOBAL` |
| North America | 2 | `AMERICA`, `CANADA` |
| Europe | 30 | See table below |
| Middle East / Africa | 12 | See table below |
| Mexico / South America | 7 | See table below |
| Asia-Pacific | 17 | See table below |
| **Total** | **69** | |

### Full Market Table

#### Global

| Enum | Value | Display Name | Exchanges |
|------|-------|--------------|-----------|
| `Market.GLOBAL` | `"global"` | Entire world | (all) |

#### North America

| Enum | Value | Display Name | Exchanges |
|------|-------|--------------|-----------|
| `Market.AMERICA` | `"america"` | USA | NASDAQ, NYSE, NYSE ARCA, OTC |
| `Market.CANADA` | `"canada"` | Canada | TSX, TSXV, CSE, NEO |

#### Europe (30 markets)

| Enum | Value | Display Name | Exchanges |
|------|-------|--------------|-----------|
| `Market.AUSTRIA` | `"austria"` | Austria | VIE |
| `Market.BELGIUM` | `"belgium"` | Belgium | EURONEXTBRU |
| `Market.SWITZERLAND` | `"switzerland"` | Switzerland | SIX, BX |
| `Market.CYPRUS` | `"cyprus"` | Cyprus | CSECY |
| `Market.CZECH` | `"czech"` | Czech Republic | PSECZ |
| `Market.GERMANY` | `"germany"` | Germany | FWB, SWB, XETR, BER, DUS, HAM, HAN, MUN, TRADEGATE, LS, LSX, GETTEX |
| `Market.DENMARK` | `"denmark"` | Denmark | OMXCOP |
| `Market.ESTONIA` | `"estonia"` | Estonia | OMXTSE |
| `Market.SPAIN` | `"spain"` | Spain | BME |
| `Market.FINLAND` | `"finland"` | Finland | OMXHEX |
| `Market.FRANCE` | `"france"` | France | EURONEXTPAR |
| `Market.GREECE` | `"greece"` | Greece | ATHEX |
| `Market.HUNGARY` | `"hungary"` | Hungary | BET |
| `Market.IRELAND` | `"ireland"` | Ireland | EURONEXTDUB |
| `Market.ICELAND` | `"iceland"` | Iceland | OMXICE |
| `Market.ITALY` | `"italy"` | Italy | MIL, EUROTLX |
| `Market.LITHUANIA` | `"lithuania"` | Lithuania | OMXVSE |
| `Market.LATVIA` | `"latvia"` | Latvia | OMXRSE |
| `Market.LUXEMBOURG` | `"luxembourg"` | Luxembourg | LUXSE |
| `Market.NETHERLANDS` | `"netherlands"` | Netherlands | EURONEXTAMS |
| `Market.NORWAY` | `"norway"` | Norway | EURONEXTOSE |
| `Market.POLAND` | `"poland"` | Poland | GPW, NEWCONNECT |
| `Market.PORTUGAL` | `"portugal"` | Portugal | EURONEXTLIS |
| `Market.SERBIA` | `"serbia"` | Serbia | BELEX |
| `Market.RUSSIA` | `"russia"` | Russia | RUS (TradingView internal code) |
| `Market.ROMANIA` | `"romania"` | Romania | BVB |
| `Market.SWEDEN` | `"sweden"` | Sweden | NGM, OMXSTO |
| `Market.SLOVAKIA` | `"slovakia"` | Slovakia | BSSE |
| `Market.TURKEY` | `"turkey"` | Turkey | BIST |
| `Market.UK` | `"uk"` | United Kingdom | LSE, LSIN, AQUIS |

#### Middle East / Africa (12 markets)

| Enum | Value | Display Name | Exchanges |
|------|-------|--------------|-----------|
| `Market.UAE` | `"uae"` | United Arab Emirates | DFM, ADX, NASDAQDUBAI |
| `Market.BAHRAIN` | `"bahrain"` | Bahrain | BAHRAIN |
| `Market.EGYPT` | `"egypt"` | Egypt | EGX |
| `Market.ISRAEL` | `"israel"` | Israel | TASE |
| `Market.KENYA` | `"kenya"` | Kenya | NSEKE |
| `Market.KUWAIT` | `"kuwait"` | Kuwait | KSE |
| `Market.MOROCCO` | `"morocco"` | Morocco | CSEMA |
| `Market.NIGERIA` | `"nigeria"` | Nigeria | NSENG |
| `Market.QATAR` | `"qatar"` | Qatar | QSE |
| `Market.KSA` | `"ksa"` | Saudi Arabia | TADAWUL |
| `Market.TUNISIA` | `"tunisia"` | Tunisia | BVMT |
| `Market.RSA` | `"rsa"` | South Africa | JSE |

#### Mexico / South America (7 markets)

| Enum | Value | Display Name | Exchanges |
|------|-------|--------------|-----------|
| `Market.ARGENTINA` | `"argentina"` | Argentina | BYMA, BCBA |
| `Market.BRAZIL` | `"brazil"` | Brazil | BMFBOVESPA |
| `Market.CHILE` | `"chile"` | Chile | BCS |
| `Market.COLOMBIA` | `"colombia"` | Colombia | BVC |
| `Market.MEXICO` | `"mexico"` | Mexico | BMV, BIVA |
| `Market.PERU` | `"peru"` | Peru | BVL |
| `Market.VENEZUELA` | `"venezuela"` | Venezuela | BVCV |

#### Asia-Pacific (17 markets)

| Enum | Value | Display Name | Exchanges |
|------|-------|--------------|-----------|
| `Market.AUSTRALIA` | `"australia"` | Australia | ASX |
| `Market.BANGLADESH` | `"bangladesh"` | Bangladesh | DSEBD |
| `Market.CHINA` | `"china"` | Mainland China | SSE, SZSE, SHFE, ZCE, CFFEX |
| `Market.HONGKONG` | `"hongkong"` | Hong Kong, China | HKEX |
| `Market.INDONESIA` | `"indonesia"` | Indonesia | IDX |
| `Market.INDIA` | `"india"` | India | BSE, NSE |
| `Market.JAPAN` | `"japan"` | Japan | TSE, NAG, FSE, SAPSE |
| `Market.KOREA` | `"korea"` | South Korea | KRX |
| `Market.SRILANKA` | `"srilanka"` | Sri Lanka | CSELK |
| `Market.MALAYSIA` | `"malaysia"` | Malaysia | MYX |
| `Market.NEWZEALAND` | `"newzealand"` | New Zealand | NZX |
| `Market.PHILIPPINES` | `"philippines"` | Philippines | PSE |
| `Market.PAKISTAN` | `"pakistan"` | Pakistan | PSX |
| `Market.SINGAPORE` | `"singapore"` | Singapore | SGX |
| `Market.THAILAND` | `"thailand"` | Thailand | SET |
| `Market.TAIWAN` | `"taiwan"` | Taiwan | TWSE, TPEX |
| `Market.VIETNAM` | `"vietnam"` | Vietnam | HOSE, HNX, UPCOM |

---

## `MarketRegion`

Convenience grouping of markets into geographic regions. These regions are defined by tvkit and are **not** part of the TradingView API — TradingView has no concept of regions; only individual market endpoints exist. Use with `get_markets_by_region()` to retrieve all markets in a region.

```python
class MarketRegion(StrEnum): ...
```

| Enum | Value | Markets |
|------|-------|---------|
| `MarketRegion.GLOBAL` | `"global"` | 1 |
| `MarketRegion.NORTH_AMERICA` | `"north_america"` | 2 |
| `MarketRegion.EUROPE` | `"europe"` | 30 |
| `MarketRegion.MIDDLE_EAST_AFRICA` | `"middle_east_africa"` | 12 |
| `MarketRegion.MEXICO_SOUTH_AMERICA` | `"mexico_south_america"` | 7 |
| `MarketRegion.ASIA_PACIFIC` | `"asia_pacific"` | 17 |

---

## `MarketInfo`

`NamedTuple` returned by `get_market_info()`.

```python
from tvkit.api.scanner.markets import MarketInfo
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Human-readable display name (e.g., `"Thailand"`) |
| `exchanges` | `list[str]` | Exchange identifiers active in this market |
| `description` | `str` | One-line description |

---

## Functions

### `get_market_info()`

```python
def get_market_info(market: Market) -> MarketInfo: ...
```

Return metadata for a single market.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `market` | `Market` | required | Market enum value |

#### Returns

`MarketInfo` — named tuple with `name`, `exchanges`, and `description`.

#### Raises

| Exception | When |
|-----------|------|
| `KeyError` | `market` has no entry in `MARKET_INFO` (should not occur for valid `Market` members) |

#### Example

```python
from tvkit.api.scanner.markets import Market, get_market_info

info = get_market_info(Market.THAILAND)
print(info.name)       # "Thailand"
print(info.exchanges)  # ["SET"]
```

---

### `get_markets_by_region()`

```python
def get_markets_by_region(region: MarketRegion) -> list[Market]: ...
```

Return all markets belonging to a region.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `region` | `MarketRegion` | required | Region enum value |

#### Returns

`list[Market]` — markets in the region, in source-definition order.

#### Example

```python
from tvkit.api.scanner.markets import MarketRegion, get_markets_by_region
from tvkit.api.scanner.models import create_scanner_request
from tvkit.api.scanner.services import ScannerService

async def scan_all_europe() -> None:
    europe = get_markets_by_region(MarketRegion.EUROPE)
    request = create_scanner_request(range_end=50)
    async with ScannerService() as service:
        for market in europe:
            result = await service.scan_market(market, request)
            print(f"{market.value}: {len(result.data)} stocks")
```

---

### `get_all_markets()`

```python
def get_all_markets() -> list[Market]: ...
```

Return every market in the `Market` enum (all 69).

#### Returns

`list[Market]` — all markets in enum-definition order.

#### Example

```python
from tvkit.api.scanner.markets import get_all_markets

markets = get_all_markets()
print(len(markets))  # 69
```

---

### `is_valid_market()`

```python
def is_valid_market(market_id: str) -> bool: ...
```

Check whether a string is a valid `Market` identifier. Useful when the market is supplied at runtime (e.g., from config or user input) before passing to `scan_market_by_id()`.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `market_id` | `str` | required | Candidate market identifier |

#### Returns

`bool` — `True` if `market_id` matches a `Market` enum value, `False` otherwise.

#### Example

```python
from tvkit.api.scanner.markets import is_valid_market

is_valid_market("america")   # True
is_valid_market("thailand")  # True
is_valid_market("THAILAND")  # False  — values are lowercase
is_valid_market("nasdaq")    # False  — exchanges are not market identifiers
is_valid_market("apac")      # False  — region names are not market identifiers
```

> **Note:** `Market` values are all lowercase. `"THAILAND"` and `"Thailand"` are not valid; only `"thailand"` is.

**Dynamic market input pattern** — validate before constructing a `Market` from runtime input:

```python
from tvkit.api.scanner.markets import Market, is_valid_market

market_id: str = "thailand"  # e.g., from CLI arg or config file

if not is_valid_market(market_id):
    raise ValueError(f"Unknown market: {market_id!r}. See Market enum for valid values.")

market = Market(market_id)
```

---

## Using `Market` with `ScannerService`

The `Market` enum is the primary way to target a specific market with `ScannerService.scan_market()`. The enum value is used directly as the endpoint path:

```python
from tvkit.api.scanner.markets import Market
from tvkit.api.scanner.models import create_scanner_request
from tvkit.api.scanner.services import ScannerService

request = create_scanner_request(range_end=20)

async with ScannerService() as service:
    result = await service.scan_market(Market.THAILAND, request)
    # Calls: POST https://scanner.tradingview.com/thailand/scan
```

When the market identifier comes from external input (config, CLI, API), use `is_valid_market()` to validate it first, then construct the enum with `Market(market_id)`, then pass it to `scan_market()`. Alternatively, pass the raw string directly to `scan_market_by_id()` — it performs the same validation internally.

> **Exchange codes** listed in the market tables above (e.g., `EURONEXTPAR`, `EURONEXTAMS`) are TradingView's internal exchange identifiers. They are informational — you do not need to pass them to any tvkit function.

---

## See Also

- [Scanner Reference](scanner.md)
- [Scanner Guide](../../guides/scanner.md)
- [Concepts: Scanner Columns](../../concepts/scanner-columns.md)
