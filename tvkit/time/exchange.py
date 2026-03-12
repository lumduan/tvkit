"""
Exchange → IANA timezone mapping for TradingView markets.

Covers all exchange codes present in ``tvkit.api.scanner.markets.MARKET_INFO``.

Lookup is layered:

1. User overrides registered via :func:`register_exchange` or :func:`load_exchange_overrides`
2. Built-in registry (``_EXCHANGE_TIMEZONES``)
3. UTC fallback with WARNING log (logged once per unknown exchange code)

Unknown exchange codes fall back to ``"UTC"`` with a WARNING log rather than raising
``ValueError`` — this prevents disruption when TradingView adds new exchanges before
the mapping is updated.

Crypto exchanges are mapped to ``"UTC"`` because they operate 24/7 with no market
open/close session and no exchange-local concept of time.
"""

import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tvkit.api.scanner.markets import MARKET_INFO

logger = logging.getLogger(__name__)

# ── Built-in registry ─────────────────────────────────────────────────────────
# IANA timezone mapping for all TradingView exchange codes in MARKET_INFO.
# Keys are uppercase exchange codes as used in TradingView symbol strings.
_EXCHANGE_TIMEZONES: dict[str, str] = {
    # ── North America ─────────────────────────────────────────────────────────
    "NASDAQ": "America/New_York",
    "NYSE": "America/New_York",
    "NYSE ARCA": "America/New_York",
    "OTC": "America/New_York",
    "TSX": "America/Toronto",
    "TSXV": "America/Toronto",
    "CSE": "America/Toronto",
    "NEO": "America/Toronto",
    # ── Europe ────────────────────────────────────────────────────────────────
    "VIE": "Europe/Vienna",  # Austria
    "EURONEXTBRU": "Europe/Brussels",  # Belgium
    "SIX": "Europe/Zurich",  # Switzerland
    "BX": "Europe/Zurich",  # Switzerland (BX Swiss)
    "CSECY": "Asia/Nicosia",  # Cyprus
    "PSECZ": "Europe/Prague",  # Czech Republic
    "FWB": "Europe/Berlin",  # Germany (Frankfurt)
    "SWB": "Europe/Berlin",  # Germany (Stuttgart)
    "XETR": "Europe/Berlin",  # Germany (XETRA)
    "BER": "Europe/Berlin",  # Germany (Berlin)
    "DUS": "Europe/Berlin",  # Germany (Düsseldorf)
    "HAM": "Europe/Berlin",  # Germany (Hamburg)
    "HAN": "Europe/Berlin",  # Germany (Hanover)
    "MUN": "Europe/Berlin",  # Germany (Munich)
    "TRADEGATE": "Europe/Berlin",  # Germany (Tradegate)
    "LS": "Europe/Berlin",  # Germany (Lang & Schwarz)
    "LSX": "Europe/Berlin",  # Germany (LSX)
    "GETTEX": "Europe/Berlin",  # Germany (gettex)
    "OMXCOP": "Europe/Copenhagen",  # Denmark
    "OMXTSE": "Europe/Tallinn",  # Estonia
    "BME": "Europe/Madrid",  # Spain
    "OMXHEX": "Europe/Helsinki",  # Finland
    "EURONEXTPAR": "Europe/Paris",  # France
    "ATHEX": "Europe/Athens",  # Greece
    "BET": "Europe/Budapest",  # Hungary
    "EURONEXTDUB": "Europe/Dublin",  # Ireland
    "OMXICE": "Atlantic/Reykjavik",  # Iceland
    "MIL": "Europe/Rome",  # Italy (Borsa Italiana)
    "EUROTLX": "Europe/Rome",  # Italy (EuroTLX)
    "OMXVSE": "Europe/Vilnius",  # Lithuania
    "OMXRSE": "Europe/Riga",  # Latvia
    "LUXSE": "Europe/Luxembourg",  # Luxembourg
    "EURONEXTAMS": "Europe/Amsterdam",  # Netherlands
    "EURONEXTOSE": "Europe/Oslo",  # Norway
    "GPW": "Europe/Warsaw",  # Poland
    "NEWCONNECT": "Europe/Warsaw",  # Poland (NewConnect)
    "EURONEXTLIS": "Europe/Lisbon",  # Portugal
    "BELEX": "Europe/Belgrade",  # Serbia
    "RUS": "Europe/Moscow",  # Russia
    "BVB": "Europe/Bucharest",  # Romania
    "NGM": "Europe/Stockholm",  # Sweden (Nordic Growth Market)
    "OMXSTO": "Europe/Stockholm",  # Sweden (Nasdaq Stockholm)
    "BSSE": "Europe/Bratislava",  # Slovakia
    "BIST": "Europe/Istanbul",  # Turkey
    "LSE": "Europe/London",  # UK (London Stock Exchange)
    "LSIN": "Europe/London",  # UK (LSE International)
    "AQUIS": "Europe/London",  # UK (Aquis Exchange)
    # ── Middle East / Africa ──────────────────────────────────────────────────
    "DFM": "Asia/Dubai",  # UAE (Dubai Financial Market)
    "ADX": "Asia/Dubai",  # UAE (Abu Dhabi Securities)
    "NASDAQDUBAI": "Asia/Dubai",  # UAE (Nasdaq Dubai)
    "BAHRAIN": "Asia/Bahrain",  # Bahrain
    "EGX": "Africa/Cairo",  # Egypt
    "TASE": "Asia/Jerusalem",  # Israel
    "NSEKE": "Africa/Nairobi",  # Kenya
    "KSE": "Asia/Kuwait",  # Kuwait
    "CSEMA": "Africa/Casablanca",  # Morocco
    "NSENG": "Africa/Lagos",  # Nigeria
    "QSE": "Asia/Qatar",  # Qatar
    "TADAWUL": "Asia/Riyadh",  # Saudi Arabia
    "BVMT": "Africa/Tunis",  # Tunisia
    "JSE": "Africa/Johannesburg",  # South Africa
    # ── Mexico / South America ────────────────────────────────────────────────
    "BYMA": "America/Argentina/Buenos_Aires",  # Argentina
    "BCBA": "America/Argentina/Buenos_Aires",  # Argentina (BCBA)
    "BMFBOVESPA": "America/Sao_Paulo",  # Brazil
    "BCS": "America/Santiago",  # Chile
    "BVC": "America/Bogota",  # Colombia
    "BMV": "America/Mexico_City",  # Mexico (Bolsa Mexicana)
    "BIVA": "America/Mexico_City",  # Mexico (BIVA)
    "BVL": "America/Lima",  # Peru
    "BVCV": "America/Caracas",  # Venezuela
    # ── Asia / Pacific ────────────────────────────────────────────────────────
    "ASX": "Australia/Sydney",  # Australia
    "DSEBD": "Asia/Dhaka",  # Bangladesh
    "SSE": "Asia/Shanghai",  # China (Shanghai Stock Exchange)
    "SZSE": "Asia/Shanghai",  # China (Shenzhen Stock Exchange)
    "SHFE": "Asia/Shanghai",  # China (Shanghai Futures)
    "ZCE": "Asia/Shanghai",  # China (Zhengzhou Commodity)
    "CFFEX": "Asia/Shanghai",  # China (China Financial Futures)
    "HKEX": "Asia/Hong_Kong",  # Hong Kong
    "IDX": "Asia/Jakarta",  # Indonesia
    "BSE": "Asia/Kolkata",  # India (Bombay Stock Exchange)
    "NSE": "Asia/Kolkata",  # India (National Stock Exchange)
    "TSE": "Asia/Tokyo",  # Japan (Tokyo Stock Exchange)
    "NAG": "Asia/Tokyo",  # Japan (Nagoya)
    "FSE": "Asia/Tokyo",  # Japan (Fukuoka)
    "SAPSE": "Asia/Tokyo",  # Japan (Sapporo)
    "KRX": "Asia/Seoul",  # South Korea
    "CSELK": "Asia/Colombo",  # Sri Lanka
    "MYX": "Asia/Kuala_Lumpur",  # Malaysia
    "NZX": "Pacific/Auckland",  # New Zealand
    "PSE": "Asia/Manila",  # Philippines
    "PSX": "Asia/Karachi",  # Pakistan
    "SGX": "Asia/Singapore",  # Singapore
    "SET": "Asia/Bangkok",  # Thailand
    "TWSE": "Asia/Taipei",  # Taiwan (TWSE)
    "TPEX": "Asia/Taipei",  # Taiwan (TPEX)
    "HOSE": "Asia/Ho_Chi_Minh",  # Vietnam (Ho Chi Minh)
    "HNX": "Asia/Ho_Chi_Minh",  # Vietnam (Hanoi)
    "UPCOM": "Asia/Ho_Chi_Minh",  # Vietnam (UPCoM)
}

# ── User override registry ────────────────────────────────────────────────────
# Populated via register_exchange() or load_exchange_overrides().
# Takes precedence over _EXCHANGE_TIMEZONES in all lookups.
_USER_EXCHANGE_TIMEZONES: dict[str, str] = {}

# Cache of unknown exchange codes for which a warning has already been logged.
# Prevents repeated WARNING lines when exchange_timezone() is called in a loop.
_WARNED_EXCHANGES: set[str] = set()


def register_exchange(exchange: str, tz: str) -> None:
    """
    Register or override an exchange → timezone mapping at runtime.

    Useful for extending the built-in registry without modifying library source.
    User registrations take precedence over the built-in ``_EXCHANGE_TIMEZONES``.

    Args:
        exchange: Exchange code (e.g. ``"MYEXCHANGE"``). Case-insensitive.
        tz: IANA timezone string (e.g. ``"Asia/Bangkok"``). Validated on registration.

    Raises:
        ValueError: If ``tz`` is not a valid IANA timezone string.

    Example:
        >>> from tvkit.time import register_exchange
        >>> register_exchange("MYEXCHANGE", "Asia/Bangkok")
        >>> from tvkit.time import exchange_timezone
        >>> exchange_timezone("MYEXCHANGE")
        'Asia/Bangkok'
    """
    try:
        ZoneInfo(tz)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Invalid IANA timezone {tz!r} for exchange {exchange!r}. "
            "See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        ) from exc

    code = str(exchange).upper()
    _USER_EXCHANGE_TIMEZONES[code] = tz
    logger.info("Registered custom exchange timezone: %s → %s", code, tz)


def load_exchange_overrides(path: str | Path) -> None:
    """
    Load exchange timezone overrides from a YAML file.

    Requires ``pyyaml`` (``uv add pyyaml``). YAML support is optional — the rest
    of ``tvkit.time`` works without it.

    The YAML file must have an ``exchanges`` key mapping exchange codes to IANA
    timezone strings:

    .. code-block:: yaml

        exchanges:
          MYEXCHANGE: Asia/Bangkok
          ANOTHER: Europe/London

    Args:
        path: Path to a YAML override file.

    Raises:
        ImportError: If ``pyyaml`` is not installed.
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file structure is invalid or a timezone string is invalid.

    Example:
        >>> from tvkit.time import load_exchange_overrides
        >>> load_exchange_overrides("tvkit_exchange_overrides.yaml")
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "load_exchange_overrides() requires pyyaml. Install it with: uv add pyyaml"
        ) from exc

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Exchange override file not found: {file_path}")

    data: object = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid override file {file_path}: expected a YAML mapping at top level")

    exchanges = data.get("exchanges", {})
    if not isinstance(exchanges, dict):
        raise ValueError(
            f"Invalid override file {file_path}: 'exchanges' must be a mapping, "
            f"got {type(exchanges).__name__!r}"
        )

    # Normalization (code.upper()) is handled inside register_exchange()
    for code, timezone in exchanges.items():
        register_exchange(str(code), str(timezone))

    logger.info("Loaded %d exchange override(s) from %s", len(exchanges), file_path)


def exchange_timezone(exchange: str) -> str:
    """
    Return the IANA timezone string for a TradingView exchange code.

    Lookup is layered:

    1. User overrides (registered via :func:`register_exchange` or
       :func:`load_exchange_overrides`)
    2. Built-in registry (``_EXCHANGE_TIMEZONES``)
    3. UTC fallback with WARNING log (logged once per unique unknown exchange code)

    Accepts both bare exchange codes (``"NASDAQ"``) and full symbol strings
    (``"NASDAQ:AAPL"``). The exchange prefix is parsed and whitespace-stripped
    transparently. Lookup is case-insensitive.

    Args:
        exchange: TradingView exchange code (e.g. ``"NASDAQ"``, ``"SET"``)
            or full symbol string (e.g. ``"NASDAQ:AAPL"``, ``"SET:PTT"``).

    Returns:
        IANA timezone string (e.g. ``"America/New_York"``, ``"Asia/Bangkok"``).
        Returns ``"UTC"`` for unknown exchanges.

    Example:
        >>> from tvkit.time import exchange_timezone
        >>> exchange_timezone("NASDAQ")
        'America/New_York'
        >>> exchange_timezone("NASDAQ:AAPL")
        'America/New_York'
        >>> exchange_timezone("SET")
        'Asia/Bangkok'
        >>> exchange_timezone("UNKNOWN_EXCHANGE")
        'UTC'
    """
    code: str = exchange.split(":", 1)[0].strip().upper()

    # 1. User overrides take precedence
    tz = _USER_EXCHANGE_TIMEZONES.get(code)
    if tz is not None:
        return tz

    # 2. Built-in registry
    tz = _EXCHANGE_TIMEZONES.get(code)
    if tz is not None:
        return tz

    # 3. UTC fallback — log once per unique unknown code to prevent log spam
    if code not in _WARNED_EXCHANGES:
        _WARNED_EXCHANGES.add(code)
        logger.warning(
            "Unknown exchange %r — falling back to UTC. "
            "Add this exchange to tvkit/time/exchange.py or register it via register_exchange().",
            code,
        )
    return "UTC"


def supported_exchanges() -> set[str]:
    """
    Return the set of all exchange codes with a known timezone mapping.

    Includes both the built-in registry and any user-registered overrides.

    Returns:
        Set of uppercase exchange code strings.

    Example:
        >>> from tvkit.time import supported_exchanges
        >>> "NASDAQ" in supported_exchanges()
        True
        >>> "SET" in supported_exchanges()
        True
    """
    return set(_EXCHANGE_TIMEZONES) | set(_USER_EXCHANGE_TIMEZONES)


def exchange_timezone_map() -> dict[str, str]:
    """
    Return the merged exchange → IANA timezone mapping.

    User overrides shadow built-in entries with the same exchange code.
    The returned dict is a copy — mutating it has no effect on the registry.

    Returns:
        Dict mapping uppercase exchange codes to IANA timezone strings.

    Example:
        >>> from tvkit.time import exchange_timezone_map
        >>> tz_map = exchange_timezone_map()
        >>> tz_map["NASDAQ"]
        'America/New_York'
    """
    merged = dict(_EXCHANGE_TIMEZONES)
    merged.update(_USER_EXCHANGE_TIMEZONES)
    return merged


def validate_exchange_registry() -> set[str]:
    """
    Validate that the registry covers all exchange codes in ``MARKET_INFO``.

    Compares all exchange codes defined in
    ``tvkit.api.scanner.markets.MARKET_INFO`` against the combined set of
    ``_EXCHANGE_TIMEZONES`` and ``_USER_EXCHANGE_TIMEZONES``. Returns the set of
    codes present in ``MARKET_INFO`` but missing from both registries.

    Use in tests to catch ``MARKET_INFO`` drift:

    .. code-block:: python

        from tvkit.time import validate_exchange_registry
        assert validate_exchange_registry() == set(), "Exchange registry is incomplete"

    Returns:
        Set of missing exchange code strings. Empty set means full coverage.

    Example:
        >>> from tvkit.time import validate_exchange_registry
        >>> missing = validate_exchange_registry()
        >>> if missing:
        ...     print(f"Missing: {sorted(missing)}")
    """
    all_market_exchanges: set[str] = {
        e.upper() for info in MARKET_INFO.values() for e in info.exchanges
    }
    combined_registry = set(_EXCHANGE_TIMEZONES.keys()) | set(_USER_EXCHANGE_TIMEZONES.keys())
    missing = all_market_exchanges - combined_registry

    if missing:
        logger.warning(
            "Exchange registry is missing %d code(s): %s — these will fall back to UTC. "
            "Update tvkit/time/exchange.py or use register_exchange().",
            len(missing),
            sorted(missing),
        )

    return missing


# ── Auto-load from environment variable ───────────────────────────────────────
# Set TVKIT_EXCHANGE_OVERRIDES=/path/to/overrides.yaml to auto-load at import time.
_env_override_path: str | None = os.getenv("TVKIT_EXCHANGE_OVERRIDES")
if _env_override_path:
    try:
        load_exchange_overrides(_env_override_path)
    except Exception as _env_exc:  # noqa: BLE001
        logger.warning(
            "Failed to load exchange overrides from TVKIT_EXCHANGE_OVERRIDES=%r: %s",
            _env_override_path,
            _env_exc,
        )
