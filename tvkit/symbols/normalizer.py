"""
Core symbol normalization functions for tvkit.

All functions in this module are **synchronous** — symbol normalization is a pure-string
transformation with no I/O. They are safe to call from both sync and async contexts.
"""

import re
from re import Pattern

from .exceptions import SymbolNormalizationError
from .models import (
    CANONICAL_PATTERN,
    NormalizationConfig,
    NormalizationType,
    NormalizedSymbol,
)

_CANONICAL_RE: Pattern[str] = re.compile(CANONICAL_PATTERN)


def _normalize_core(
    symbol: str,
    config: NormalizationConfig,
) -> tuple[str, NormalizationType]:
    """
    Apply normalization rules and return ``(canonical, normalization_type)``.

    Rules applied in order:
    1. Strip leading/trailing whitespace (if ``config.strip_whitespace`` is True)
    2. Raise if empty after strip
    2b. Bare-ticker resolution: if no ``:`` and no ``-`` and ``config.default_exchange`` is set,
        prepend the default exchange
    3. Uppercase entire string
    4. If no ``:`` and exactly one ``-``: replace first ``-`` with ``:``
    5. Validate against canonical pattern using fullmatch; raise on mismatch
    6. Determine primary NormalizationType

    Args:
        symbol: Already type-checked ``str`` from a public entry point.
        config: Normalization configuration.

    Returns:
        Tuple of (canonical string, primary NormalizationType).

    Raises:
        SymbolNormalizationError: If the symbol cannot be normalised.
    """
    raw: str = symbol

    # --- Step 1: optional whitespace strip ---
    had_leading_or_trailing: bool = symbol != symbol.strip()
    if config.strip_whitespace:
        symbol = symbol.strip()

    # --- Step 2: empty check ---
    if not symbol:
        reason: str = (
            "symbol must not be empty after stripping whitespace"
            if had_leading_or_trailing
            else "symbol must not be empty"
        )
        raise SymbolNormalizationError(original=raw, reason=reason)

    # --- Step 2b: bare-ticker resolution via default_exchange ---
    # Fires only when no ':' and no '-' are present.
    # Dash-notation symbols (e.g. NASDAQ-AAPL) are NOT bare tickers — they are handled
    # by the dash→colon rule in Step 4.
    used_default_exchange: bool = False
    if ":" not in symbol and "-" not in symbol and config.default_exchange is not None:
        symbol = f"{config.default_exchange}:{symbol}"
        used_default_exchange = True

    # --- Step 3: uppercase ---
    uppercased: str = symbol.upper()

    # --- Step 4: dash → colon (only when no colon present and exactly one dash) ---
    used_dash_conversion: bool = False
    converted: str
    if ":" not in uppercased and uppercased.count("-") == 1:
        converted = uppercased.replace("-", ":", 1)
        used_dash_conversion = True
    else:
        converted = uppercased

    # --- Step 5: validate using fullmatch for strict anchoring ---
    if not _CANONICAL_RE.fullmatch(converted):
        colon_count: int = converted.count(":")
        has_whitespace: bool = any(ch.isspace() for ch in converted)

        if colon_count > 1:
            reason = "symbol contains multiple ':' separators"
        elif converted.startswith(":"):
            reason = "exchange component must not be empty after normalization"
        elif converted.endswith(":"):
            reason = "ticker component must not be empty after normalization"
        elif has_whitespace:
            # Distinguish leading/trailing whitespace (strip_whitespace=False path)
            # from truly internal whitespace (e.g. "INVALID SYMBOL").
            if not config.strip_whitespace and had_leading_or_trailing:
                reason = (
                    "symbol has leading or trailing whitespace; "
                    "set strip_whitespace=True or strip the input before normalizing"
                )
            else:
                reason = "symbol must not contain internal whitespace"
        elif colon_count == 0:
            reason = "no exchange prefix"
        else:
            reason = "symbol components must contain only valid characters"
        raise SymbolNormalizationError(original=raw, reason=reason)

    # --- Step 6: determine primary normalization type ---
    norm_type: NormalizationType
    if had_leading_or_trailing and config.strip_whitespace:
        norm_type = NormalizationType.WHITESPACE_STRIP
    elif used_default_exchange:
        norm_type = NormalizationType.DEFAULT_EXCHANGE
    elif used_dash_conversion:
        norm_type = NormalizationType.DASH_TO_COLON
    elif symbol != converted:
        norm_type = NormalizationType.UPPERCASE_ONLY
    else:
        norm_type = NormalizationType.ALREADY_CANONICAL

    return converted, norm_type


def normalize_symbol(
    symbol: str,
    *,
    config: NormalizationConfig | None = None,
) -> str:
    """
    Normalize a TradingView symbol to canonical ``EXCHANGE:SYMBOL`` form.

    This function is **synchronous** — it performs a pure-string transformation with no I/O.
    It is safe to call from both sync and async contexts.

    Normalization rules applied in order:

    1. Strip leading/trailing whitespace (when ``config.strip_whitespace`` is True, the default)
    2. Raise ``SymbolNormalizationError`` if the string is empty after stripping
    3. If no ``:`` and no ``-`` are present, and ``config.default_exchange`` is set: prepend it
    4. Uppercase the entire string
    5. If no ``:`` is present and exactly one ``-`` is present: replace the ``-`` with ``:``
    6. Validate against ``^[A-Z0-9_]+:[A-Z0-9._!]+$`` — raise if the pattern does not match
    7. Return the canonical string

    Supported symbol formats:

    +-----------------------+--------------------+
    | Input                 | Output             |
    +=======================+====================+
    | ``NASDAQ:AAPL``       | ``NASDAQ:AAPL``    |
    | ``nasdaq:aapl``       | ``NASDAQ:AAPL``    |
    | ``NASDAQ-AAPL``       | ``NASDAQ:AAPL``    |
    | ``nasdaq-aapl``       | ``NASDAQ:AAPL``    |
    | ``  NASDAQ:AAPL  ``   | ``NASDAQ:AAPL``    |
    | ``FX_IDC:eurusd``     | ``FX_IDC:EURUSD``  |
    | ``NYSE:BRK.B``        | ``NYSE:BRK.B``     |
    | ``BINANCE:BTCUSDT``   | ``BINANCE:BTCUSDT``|
    +-----------------------+--------------------+

    **Bare-ticker resolution (Phase 2):** when ``config.default_exchange`` is set, bare tickers
    (no exchange prefix, no dash) are resolved using that exchange:

    .. code-block:: python

        config = NormalizationConfig(default_exchange="NASDAQ")
        normalize_symbol("AAPL", config=config)   # → "NASDAQ:AAPL"
        normalize_symbol("aapl", config=config)   # → "NASDAQ:AAPL"

    Without a ``default_exchange``, bare tickers raise ``SymbolNormalizationError``.

    **Env var support:** ``NormalizationConfig`` reads ``TVKIT_DEFAULT_EXCHANGE`` from the
    environment lazily at construction time. When ``config`` is ``None``, a fresh
    ``NormalizationConfig()`` is instantiated on each call, so the env var is read at call
    time — not at import time.

    .. warning::

        Set ``TVKIT_DEFAULT_EXCHANGE`` **before calling** this function. Passing an explicit
        ``config`` object is always the most predictable approach.

    Args:
        symbol: TradingView symbol string in any supported variant. Must be a ``str``.
        config: Optional normalization configuration. When ``None``, a fresh
            ``NormalizationConfig()`` is instantiated (reads env vars at call time).

    Returns:
        Canonical symbol string in ``EXCHANGE:SYMBOL`` format (uppercase, colon-separated).

    Raises:
        SymbolNormalizationError: If the symbol cannot be normalized to canonical form,
            or if ``symbol`` is not a ``str``.

    Example:
        >>> normalize_symbol("nasdaq:aapl")
        'NASDAQ:AAPL'
        >>> normalize_symbol("NASDAQ-AAPL")
        'NASDAQ:AAPL'
        >>> normalize_symbol("  NASDAQ:AAPL  ")
        'NASDAQ:AAPL'
        >>> normalize_symbol("FX_IDC:eurusd")
        'FX_IDC:EURUSD'
        >>> from tvkit.symbols import NormalizationConfig
        >>> normalize_symbol("AAPL", config=NormalizationConfig(default_exchange="NASDAQ"))
        'NASDAQ:AAPL'
        >>> normalize_symbol("AAPL")
        Traceback (most recent call last):
            ...
        tvkit.symbols.exceptions.SymbolNormalizationError: Cannot normalize 'AAPL': no exchange prefix
    """
    if not isinstance(symbol, str):
        raise SymbolNormalizationError(
            original=repr(symbol),
            reason=f"symbol must be a str, got {type(symbol).__name__}",
        )
    cfg: NormalizationConfig = config if config is not None else NormalizationConfig()
    canonical, _ = _normalize_core(symbol, cfg)
    return canonical


def normalize_symbols(
    symbols: list[str],
    *,
    config: NormalizationConfig | None = None,
) -> list[str]:
    """
    Normalize a list of TradingView symbols to canonical ``EXCHANGE:SYMBOL`` form.

    This is a **1:1 batch** variant of ``normalize_symbol``:

    - Input order is preserved in the output.
    - Duplicate inputs produce duplicate outputs (no deduplication).
    - Raises ``SymbolNormalizationError`` on the **first** invalid symbol encountered.

    Args:
        symbols: List of TradingView symbol strings. Must be a ``list``; passing a single
            ``str`` raises ``SymbolNormalizationError`` to avoid silent character-by-character
            iteration. Each element must be a ``str``.
        config: Optional normalization configuration. When ``None``, a fresh
            ``NormalizationConfig()`` is instantiated once and shared across all elements
            in the batch (reads env vars at call time).

    Returns:
        List of canonical symbol strings, same length and order as the input.

    Raises:
        SymbolNormalizationError: If ``symbols`` is not a ``list``, or if any element
            cannot be normalized (raised on first error).

    Example:
        >>> normalize_symbols(["NASDAQ:AAPL", "BINANCE:btcusdt"])
        ['NASDAQ:AAPL', 'BINANCE:BTCUSDT']
        >>> normalize_symbols([])
        []
        >>> normalize_symbols(["NASDAQ:AAPL", "NASDAQ:AAPL"])  # duplicates preserved
        ['NASDAQ:AAPL', 'NASDAQ:AAPL']
    """
    if not isinstance(symbols, list):
        raise SymbolNormalizationError(
            original=repr(symbols),
            reason=(
                f"symbols must be a list of str, got {type(symbols).__name__}; "
                "pass a single symbol to normalize_symbol() instead"
            ),
        )
    cfg: NormalizationConfig = config if config is not None else NormalizationConfig()
    return [normalize_symbol(s, config=cfg) for s in symbols]


def normalize_symbol_detailed(
    symbol: str,
    *,
    config: NormalizationConfig | None = None,
) -> NormalizedSymbol:
    """
    Normalize a TradingView symbol and return a rich result model with metadata.

    Applies the same normalization rules as ``normalize_symbol`` but returns a
    ``NormalizedSymbol`` model that includes the canonical form, the split exchange and
    ticker components, the original input, and the primary normalization type applied.

    Use this function when you need to inspect *how* a symbol was normalized (e.g. for
    audit logging, debugging, or pipeline tracing). For most call sites, the simpler
    ``normalize_symbol`` returning a plain ``str`` is preferred.

    Args:
        symbol: TradingView symbol string in any supported variant. Must be a ``str``.
        config: Optional normalization configuration. When ``None``, a fresh
            ``NormalizationConfig()`` is instantiated (reads env vars at call time).

    Returns:
        ``NormalizedSymbol`` with ``canonical``, ``exchange``, ``ticker``, ``original``,
        and ``normalization_type`` populated.

    Raises:
        SymbolNormalizationError: If the symbol cannot be normalized to canonical form,
            or if ``symbol`` is not a ``str``.

    Example:
        >>> result = normalize_symbol_detailed("NASDAQ-AAPL")
        >>> result.canonical          # "NASDAQ:AAPL"
        >>> result.exchange           # "NASDAQ"
        >>> result.ticker             # "AAPL"
        >>> result.original           # "NASDAQ-AAPL"
        >>> result.normalization_type # NormalizationType.DASH_TO_COLON
        >>> from tvkit.symbols import NormalizationConfig, NormalizationType
        >>> result2 = normalize_symbol_detailed("AAPL", config=NormalizationConfig(default_exchange="NASDAQ"))
        >>> result2.normalization_type # NormalizationType.DEFAULT_EXCHANGE
    """
    if not isinstance(symbol, str):
        raise SymbolNormalizationError(
            original=repr(symbol),
            reason=f"symbol must be a str, got {type(symbol).__name__}",
        )
    cfg: NormalizationConfig = config if config is not None else NormalizationConfig()
    canonical, norm_type = _normalize_core(symbol, cfg)
    exchange, ticker = canonical.split(":", 1)
    return NormalizedSymbol(
        canonical=canonical,
        exchange=exchange,
        ticker=ticker,
        original=symbol,
        normalization_type=norm_type,
    )
