"""
TradingView Scanner Markets.

This module provides market identifiers and metadata for TradingView's scanner API.
All market identifiers are extracted from TradingView's official market selection dialog.
"""

from enum import Enum
from typing import Dict, List, NamedTuple


class MarketInfo(NamedTuple):
    """Market information containing display name and exchanges."""

    name: str
    exchanges: List[str]
    description: str


class Market(str, Enum):
    """
    Available markets for TradingView scanner API.

    Values correspond to the market identifiers used in scanner API endpoints.
    """

    # Global
    GLOBAL = "global"

    # North America
    AMERICA = "america"  # USA
    CANADA = "canada"

    # Europe
    AUSTRIA = "austria"
    BELGIUM = "belgium"
    SWITZERLAND = "switzerland"
    CYPRUS = "cyprus"
    CZECH = "czech"  # Czech Republic
    GERMANY = "germany"
    DENMARK = "denmark"
    ESTONIA = "estonia"
    SPAIN = "spain"
    FINLAND = "finland"
    FRANCE = "france"
    GREECE = "greece"
    HUNGARY = "hungary"
    IRELAND = "ireland"
    ICELAND = "iceland"
    ITALY = "italy"
    LITHUANIA = "lithuania"
    LATVIA = "latvia"
    LUXEMBOURG = "luxembourg"
    NETHERLANDS = "netherlands"
    NORWAY = "norway"
    POLAND = "poland"
    PORTUGAL = "portugal"
    SERBIA = "serbia"
    RUSSIA = "russia"
    ROMANIA = "romania"
    SWEDEN = "sweden"
    SLOVAKIA = "slovakia"
    TURKEY = "turkey"
    UK = "uk"  # United Kingdom

    # Middle East / Africa
    UAE = "uae"  # United Arab Emirates
    BAHRAIN = "bahrain"
    EGYPT = "egypt"
    ISRAEL = "israel"
    KENYA = "kenya"
    KUWAIT = "kuwait"
    MOROCCO = "morocco"
    NIGERIA = "nigeria"
    QATAR = "qatar"
    KSA = "ksa"  # Saudi Arabia
    TUNISIA = "tunisia"
    RSA = "rsa"  # South Africa

    # Mexico and South America
    ARGENTINA = "argentina"
    BRAZIL = "brazil"
    CHILE = "chile"
    COLOMBIA = "colombia"
    MEXICO = "mexico"
    PERU = "peru"
    VENEZUELA = "venezuela"

    # Asia / Pacific
    AUSTRALIA = "australia"
    BANGLADESH = "bangladesh"
    CHINA = "china"  # Mainland China
    HONGKONG = "hongkong"  # Hong Kong, China
    INDONESIA = "indonesia"
    INDIA = "india"
    JAPAN = "japan"
    KOREA = "korea"  # South Korea
    SRILANKA = "srilanka"  # Sri Lanka
    MALAYSIA = "malaysia"
    NEWZEALAND = "newzealand"  # New Zealand
    PHILIPPINES = "philippines"
    PAKISTAN = "pakistan"
    SINGAPORE = "singapore"
    THAILAND = "thailand"
    TAIWAN = "taiwan"  # Taiwan, China
    VIETNAM = "vietnam"


# Market metadata with exchange information
MARKET_INFO: Dict[Market, MarketInfo] = {
    # Global
    Market.GLOBAL: MarketInfo(
        name="Entire world", exchanges=[], description="Global markets overview"
    ),
    # North America
    Market.AMERICA: MarketInfo(
        name="USA",
        exchanges=["NASDAQ", "NYSE", "NYSE ARCA", "OTC"],
        description="United States stock markets",
    ),
    Market.CANADA: MarketInfo(
        name="Canada",
        exchanges=["TSX", "TSXV", "CSE", "NEO"],
        description="Canadian stock markets",
    ),
    # Europe
    Market.AUSTRIA: MarketInfo(
        name="Austria", exchanges=["VIE"], description="Austrian stock market"
    ),
    Market.BELGIUM: MarketInfo(
        name="Belgium", exchanges=["EURONEXTBRU"], description="Belgian stock market"
    ),
    Market.SWITZERLAND: MarketInfo(
        name="Switzerland", exchanges=["SIX", "BX"], description="Swiss stock markets"
    ),
    Market.CYPRUS: MarketInfo(
        name="Cyprus", exchanges=["CSECY"], description="Cyprus stock market"
    ),
    Market.CZECH: MarketInfo(
        name="Czech Republic", exchanges=["PSECZ"], description="Czech stock market"
    ),
    Market.GERMANY: MarketInfo(
        name="Germany",
        exchanges=[
            "FWB",
            "SWB",
            "XETR",
            "BER",
            "DUS",
            "HAM",
            "HAN",
            "MUN",
            "TRADEGATE",
            "LS",
            "LSX",
            "GETTEX",
        ],
        description="German stock markets",
    ),
    Market.DENMARK: MarketInfo(
        name="Denmark", exchanges=["OMXCOP"], description="Danish stock market"
    ),
    Market.ESTONIA: MarketInfo(
        name="Estonia", exchanges=["OMXTSE"], description="Estonian stock market"
    ),
    Market.SPAIN: MarketInfo(
        name="Spain", exchanges=["BME"], description="Spanish stock market"
    ),
    Market.FINLAND: MarketInfo(
        name="Finland", exchanges=["OMXHEX"], description="Finnish stock market"
    ),
    Market.FRANCE: MarketInfo(
        name="France", exchanges=["EURONEXTPAR"], description="French stock market"
    ),
    Market.GREECE: MarketInfo(
        name="Greece", exchanges=["ATHEX"], description="Greek stock market"
    ),
    Market.HUNGARY: MarketInfo(
        name="Hungary", exchanges=["BET"], description="Hungarian stock market"
    ),
    Market.IRELAND: MarketInfo(
        name="Ireland", exchanges=["EURONEXTDUB"], description="Irish stock market"
    ),
    Market.ICELAND: MarketInfo(
        name="Iceland", exchanges=["OMXICE"], description="Icelandic stock market"
    ),
    Market.ITALY: MarketInfo(
        name="Italy", exchanges=["MIL", "EUROTLX"], description="Italian stock markets"
    ),
    Market.LITHUANIA: MarketInfo(
        name="Lithuania", exchanges=["OMXVSE"], description="Lithuanian stock market"
    ),
    Market.LATVIA: MarketInfo(
        name="Latvia", exchanges=["OMXRSE"], description="Latvian stock market"
    ),
    Market.LUXEMBOURG: MarketInfo(
        name="Luxembourg", exchanges=["LUXSE"], description="Luxembourg stock market"
    ),
    Market.NETHERLANDS: MarketInfo(
        name="Netherlands", exchanges=["EURONEXTAMS"], description="Dutch stock market"
    ),
    Market.NORWAY: MarketInfo(
        name="Norway", exchanges=["EURONEXTOSE"], description="Norwegian stock market"
    ),
    Market.POLAND: MarketInfo(
        name="Poland",
        exchanges=["GPW", "NEWCONNECT"],
        description="Polish stock markets",
    ),
    Market.PORTUGAL: MarketInfo(
        name="Portugal",
        exchanges=["EURONEXTLIS"],
        description="Portuguese stock market",
    ),
    Market.SERBIA: MarketInfo(
        name="Serbia", exchanges=["BELEX"], description="Serbian stock market"
    ),
    Market.RUSSIA: MarketInfo(
        name="Russia", exchanges=["RUS"], description="Russian stock market"
    ),
    Market.ROMANIA: MarketInfo(
        name="Romania", exchanges=["BVB"], description="Romanian stock market"
    ),
    Market.SWEDEN: MarketInfo(
        name="Sweden", exchanges=["NGM", "OMXSTO"], description="Swedish stock markets"
    ),
    Market.SLOVAKIA: MarketInfo(
        name="Slovakia", exchanges=["BSSE"], description="Slovakian stock market"
    ),
    Market.TURKEY: MarketInfo(
        name="Turkey", exchanges=["BIST"], description="Turkish stock market"
    ),
    Market.UK: MarketInfo(
        name="United Kingdom",
        exchanges=["LSE", "LSIN", "AQUIS"],
        description="UK stock markets",
    ),
    # Middle East / Africa
    Market.UAE: MarketInfo(
        name="United Arab Emirates",
        exchanges=["DFM", "ADX", "NASDAQDUBAI"],
        description="UAE stock markets",
    ),
    Market.BAHRAIN: MarketInfo(
        name="Bahrain", exchanges=["BAHRAIN"], description="Bahrain stock market"
    ),
    Market.EGYPT: MarketInfo(
        name="Egypt", exchanges=["EGX"], description="Egyptian stock market"
    ),
    Market.ISRAEL: MarketInfo(
        name="Israel", exchanges=["TASE"], description="Israeli stock market"
    ),
    Market.KENYA: MarketInfo(
        name="Kenya", exchanges=["NSEKE"], description="Kenyan stock market"
    ),
    Market.KUWAIT: MarketInfo(
        name="Kuwait", exchanges=["KSE"], description="Kuwaiti stock market"
    ),
    Market.MOROCCO: MarketInfo(
        name="Morocco", exchanges=["CSEMA"], description="Moroccan stock market"
    ),
    Market.NIGERIA: MarketInfo(
        name="Nigeria", exchanges=["NSENG"], description="Nigerian stock market"
    ),
    Market.QATAR: MarketInfo(
        name="Qatar", exchanges=["QSE"], description="Qatari stock market"
    ),
    Market.KSA: MarketInfo(
        name="Saudi Arabia",
        exchanges=["TADAWUL"],
        description="Saudi Arabian stock market",
    ),
    Market.TUNISIA: MarketInfo(
        name="Tunisia", exchanges=["BVMT"], description="Tunisian stock market"
    ),
    Market.RSA: MarketInfo(
        name="South Africa", exchanges=["JSE"], description="South African stock market"
    ),
    # Mexico and South America
    Market.ARGENTINA: MarketInfo(
        name="Argentina",
        exchanges=["BYMA", "BCBA"],
        description="Argentine stock markets",
    ),
    Market.BRAZIL: MarketInfo(
        name="Brazil", exchanges=["BMFBOVESPA"], description="Brazilian stock market"
    ),
    Market.CHILE: MarketInfo(
        name="Chile", exchanges=["BCS"], description="Chilean stock market"
    ),
    Market.COLOMBIA: MarketInfo(
        name="Colombia", exchanges=["BVC"], description="Colombian stock market"
    ),
    Market.MEXICO: MarketInfo(
        name="Mexico", exchanges=["BMV", "BIVA"], description="Mexican stock markets"
    ),
    Market.PERU: MarketInfo(
        name="Peru", exchanges=["BVL"], description="Peruvian stock market"
    ),
    Market.VENEZUELA: MarketInfo(
        name="Venezuela", exchanges=["BVCV"], description="Venezuelan stock market"
    ),
    # Asia / Pacific
    Market.AUSTRALIA: MarketInfo(
        name="Australia", exchanges=["ASX"], description="Australian stock market"
    ),
    Market.BANGLADESH: MarketInfo(
        name="Bangladesh", exchanges=["DSEBD"], description="Bangladeshi stock market"
    ),
    Market.CHINA: MarketInfo(
        name="Mainland China",
        exchanges=["SSE", "SZSE", "SHFE", "ZCE", "CFFEX"],
        description="Chinese mainland stock markets",
    ),
    Market.HONGKONG: MarketInfo(
        name="Hong Kong, China",
        exchanges=["HKEX"],
        description="Hong Kong stock market",
    ),
    Market.INDONESIA: MarketInfo(
        name="Indonesia", exchanges=["IDX"], description="Indonesian stock market"
    ),
    Market.INDIA: MarketInfo(
        name="India", exchanges=["BSE", "NSE"], description="Indian stock markets"
    ),
    Market.JAPAN: MarketInfo(
        name="Japan",
        exchanges=["TSE", "NAG", "FSE", "SAPSE"],
        description="Japanese stock markets",
    ),
    Market.KOREA: MarketInfo(
        name="South Korea", exchanges=["KRX"], description="South Korean stock market"
    ),
    Market.SRILANKA: MarketInfo(
        name="Sri Lanka", exchanges=["CSELK"], description="Sri Lankan stock market"
    ),
    Market.MALAYSIA: MarketInfo(
        name="Malaysia", exchanges=["MYX"], description="Malaysian stock market"
    ),
    Market.NEWZEALAND: MarketInfo(
        name="New Zealand", exchanges=["NZX"], description="New Zealand stock market"
    ),
    Market.PHILIPPINES: MarketInfo(
        name="Philippines", exchanges=["PSE"], description="Philippine stock market"
    ),
    Market.PAKISTAN: MarketInfo(
        name="Pakistan", exchanges=["PSX"], description="Pakistani stock market"
    ),
    Market.SINGAPORE: MarketInfo(
        name="Singapore", exchanges=["SGX"], description="Singapore stock market"
    ),
    Market.THAILAND: MarketInfo(
        name="Thailand", exchanges=["SET"], description="Thai stock market"
    ),
    Market.TAIWAN: MarketInfo(
        name="Taiwan, China",
        exchanges=["TWSE", "TPEX"],
        description="Taiwan stock markets",
    ),
    Market.VIETNAM: MarketInfo(
        name="Vietnam",
        exchanges=["HOSE", "HNX", "UPCOM"],
        description="Vietnamese stock markets",
    ),
}


class MarketRegion(str, Enum):
    """Market regions for grouping markets."""

    GLOBAL = "global"
    NORTH_AMERICA = "north_america"
    EUROPE = "europe"
    MIDDLE_EAST_AFRICA = "middle_east_africa"
    MEXICO_SOUTH_AMERICA = "mexico_south_america"
    ASIA_PACIFIC = "asia_pacific"


# Market groupings by region
MARKETS_BY_REGION: Dict[MarketRegion, List[Market]] = {
    MarketRegion.GLOBAL: [
        Market.GLOBAL,
    ],
    MarketRegion.NORTH_AMERICA: [
        Market.AMERICA,
        Market.CANADA,
    ],
    MarketRegion.EUROPE: [
        Market.AUSTRIA,
        Market.BELGIUM,
        Market.SWITZERLAND,
        Market.CYPRUS,
        Market.CZECH,
        Market.GERMANY,
        Market.DENMARK,
        Market.ESTONIA,
        Market.SPAIN,
        Market.FINLAND,
        Market.FRANCE,
        Market.GREECE,
        Market.HUNGARY,
        Market.IRELAND,
        Market.ICELAND,
        Market.ITALY,
        Market.LITHUANIA,
        Market.LATVIA,
        Market.LUXEMBOURG,
        Market.NETHERLANDS,
        Market.NORWAY,
        Market.POLAND,
        Market.PORTUGAL,
        Market.SERBIA,
        Market.RUSSIA,
        Market.ROMANIA,
        Market.SWEDEN,
        Market.SLOVAKIA,
        Market.TURKEY,
        Market.UK,
    ],
    MarketRegion.MIDDLE_EAST_AFRICA: [
        Market.UAE,
        Market.BAHRAIN,
        Market.EGYPT,
        Market.ISRAEL,
        Market.KENYA,
        Market.KUWAIT,
        Market.MOROCCO,
        Market.NIGERIA,
        Market.QATAR,
        Market.KSA,
        Market.TUNISIA,
        Market.RSA,
    ],
    MarketRegion.MEXICO_SOUTH_AMERICA: [
        Market.ARGENTINA,
        Market.BRAZIL,
        Market.CHILE,
        Market.COLOMBIA,
        Market.MEXICO,
        Market.PERU,
        Market.VENEZUELA,
    ],
    MarketRegion.ASIA_PACIFIC: [
        Market.AUSTRALIA,
        Market.BANGLADESH,
        Market.CHINA,
        Market.HONGKONG,
        Market.INDONESIA,
        Market.INDIA,
        Market.JAPAN,
        Market.KOREA,
        Market.SRILANKA,
        Market.MALAYSIA,
        Market.NEWZEALAND,
        Market.PHILIPPINES,
        Market.PAKISTAN,
        Market.SINGAPORE,
        Market.THAILAND,
        Market.TAIWAN,
        Market.VIETNAM,
    ],
}


def get_market_info(market: Market) -> MarketInfo:
    """
    Get market information for a given market.

    Args:
        market: Market enum value

    Returns:
        MarketInfo with name, exchanges, and description

    Example:
        >>> info = get_market_info(Market.THAILAND)
        >>> print(info.name)  # "Thailand"
        >>> print(info.exchanges)  # ["SET"]
    """
    return MARKET_INFO[market]


def get_markets_by_region(region: MarketRegion) -> List[Market]:
    """
    Get all markets in a specific region.

    Args:
        region: Market region

    Returns:
        List of markets in the region

    Example:
        >>> asia_markets = get_markets_by_region(MarketRegion.ASIA_PACIFIC)
        >>> Market.THAILAND in asia_markets  # True
    """
    return MARKETS_BY_REGION[region]


def get_all_markets() -> List[Market]:
    """
    Get all available markets.

    Returns:
        List of all market enum values

    Example:
        >>> all_markets = get_all_markets()
        >>> len(all_markets)  # 69 markets
    """
    return list(Market)


def is_valid_market(market_id: str) -> bool:
    """
    Check if a market identifier is valid.

    Args:
        market_id: Market identifier string

    Returns:
        True if valid market identifier

    Example:
        >>> is_valid_market("thailand")  # True
        >>> is_valid_market("invalid")   # False
    """
    try:
        Market(market_id)
        return True
    except ValueError:
        return False
