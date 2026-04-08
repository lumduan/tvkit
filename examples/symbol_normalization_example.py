"""
Symbol normalization examples — tvkit.symbols.

Demonstrates Phase 1 (exchange-aware normalization), Phase 2 (bare-ticker resolution
via NormalizationConfig and TVKIT_DEFAULT_EXCHANGE env var), and Phase 3 (integration
pattern with the OHLCV client).

Run:
    uv run python examples/symbol_normalization_example.py
"""

import asyncio
import logging
import os
import unittest.mock

from tvkit.symbols import (
    NormalizationConfig,
    NormalizationType,
    SymbolNormalizationError,
    normalize_symbol,
    normalize_symbol_detailed,
    normalize_symbols,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def phase1_exchange_aware() -> None:
    """Phase 1: normalize symbols that already carry exchange information."""
    logger.info("--- Phase 1: exchange-aware normalization ---")

    examples = [
        "NASDAQ:AAPL",  # already canonical
        "nasdaq:aapl",  # lowercase
        "NASDAQ-AAPL",  # dash notation
        "nasdaq-aapl",  # dash + lowercase
        "  NASDAQ:AAPL  ",  # whitespace padding
        "FX_IDC:eurusd",  # exchange with underscore
        "NYSE:BRK.B",  # ticker with dot
        "CME_MINI:ES1!",  # continuous futures
        "BINANCE:btcusdt",  # crypto
    ]

    for sym in examples:
        canonical = normalize_symbol(sym)
        logger.info("  %-24r → %s", sym, canonical)


def phase1_detailed_result() -> None:
    """Phase 1: inspect normalization metadata via normalize_symbol_detailed."""
    logger.info("\n--- Phase 1: detailed result ---")

    result = normalize_symbol_detailed("NASDAQ-AAPL")
    logger.info("  canonical          : %s", result.canonical)
    logger.info("  exchange           : %s", result.exchange)
    logger.info("  ticker             : %s", result.ticker)
    logger.info("  original           : %s", result.original)
    logger.info("  normalization_type : %s", result.normalization_type)

    result2 = normalize_symbol_detailed("  nasdaq:aapl  ")
    logger.info("  whitespace input normalization_type: %s", result2.normalization_type)


def phase1_batch() -> None:
    """Phase 1: batch normalization with normalize_symbols."""
    logger.info("\n--- Phase 1: batch normalization ---")

    inputs = ["NASDAQ:AAPL", "BINANCE:btcusdt", "nyse:jpm", "  FX_IDC:EURUSD  "]
    canonicals = normalize_symbols(inputs)
    for original, canonical in zip(inputs, canonicals, strict=True):
        logger.info("  %-26r → %s", original, canonical)


def phase2_explicit_config() -> None:
    """Phase 2: bare-ticker resolution via explicit NormalizationConfig."""
    logger.info("\n--- Phase 2: bare-ticker via explicit config ---")

    config = NormalizationConfig(default_exchange="NASDAQ")

    bare_tickers = ["AAPL", "aapl", "MSFT", "GOOGL"]
    for sym in bare_tickers:
        canonical = normalize_symbol(sym, config=config)
        logger.info("  %-8s → %s", sym, canonical)

    # Exchange-aware symbols are NOT overridden by default_exchange
    override_test = normalize_symbol("BINANCE:BTCUSDT", config=config)
    logger.info(
        "  BINANCE:BTCUSDT (exchange-aware) → %s  [default_exchange ignored]", override_test
    )

    # Detailed result shows NormalizationType.DEFAULT_EXCHANGE
    result = normalize_symbol_detailed("AAPL", config=config)
    logger.info("  normalization_type for bare ticker: %s", result.normalization_type)
    assert result.normalization_type == NormalizationType.DEFAULT_EXCHANGE


def phase2_env_var() -> None:
    """
    Phase 2: bare-ticker resolution via TVKIT_DEFAULT_EXCHANGE env var.

    In production, set the env var before starting the process:
        export TVKIT_DEFAULT_EXCHANGE=NASDAQ

    In code, NormalizationConfig() reads it lazily at construction time:
        config = NormalizationConfig()   # reads TVKIT_DEFAULT_EXCHANGE
    """
    logger.info("\n--- Phase 2: TVKIT_DEFAULT_EXCHANGE env var ---")

    # Simulate setting the env var programmatically (normally done in shell/config)
    os.environ["TVKIT_DEFAULT_EXCHANGE"] = "NYSE"

    config = NormalizationConfig()  # reads TVKIT_DEFAULT_EXCHANGE at construction time
    logger.info("  NormalizationConfig().default_exchange = %r", config.default_exchange)

    canonical = normalize_symbol("JPM", config=config)
    logger.info("  normalize_symbol('JPM', config=config) → %s", canonical)

    # Clean up for other examples
    del os.environ["TVKIT_DEFAULT_EXCHANGE"]


def error_handling() -> None:
    """Error handling: SymbolNormalizationError on invalid inputs."""
    logger.info("\n--- Error handling ---")

    invalid_cases = [
        ("AAPL", "bare ticker without default_exchange"),
        ("", "empty string"),
        ("INVALID SYMBOL", "internal whitespace"),
        ("A:B:C", "multiple colons"),
    ]

    for sym, description in invalid_cases:
        try:
            normalize_symbol(sym)
        except SymbolNormalizationError as exc:
            logger.info("  %-20s (%s): %s", repr(sym), description, exc)


def phase3_ohlcv_integration_pattern() -> None:
    """
    Phase 3: demonstrate the normalize → validate ordering used inside OHLCV methods.

    OHLCV client methods call normalize_symbol before validate_symbols, so lowercase,
    dash-format, and whitespace-padded inputs all work. This function shows the same
    pattern in isolation — validate_symbols is mocked so no live network call is made.
    """
    logger.info("\n--- Phase 3: normalize → validate integration pattern ---")

    # Patch validate_symbols so we can demonstrate the pattern without a network call
    mock_validate = unittest.mock.AsyncMock(return_value=None)

    with unittest.mock.patch("tvkit.api.utils.validate_symbols", mock_validate):

        async def _demo() -> None:
            from tvkit.api.utils import validate_symbols

            # All three raw inputs normalize to the same canonical symbol before validation
            raw_inputs = ["nasdaq:aapl", "NASDAQ-AAPL", "  NASDAQ:AAPL  "]
            for raw in raw_inputs:
                canonical = normalize_symbol(raw)
                await validate_symbols(canonical)
                logger.info(
                    "  raw=%-24r  canonical=%s  validated=True",
                    raw,
                    canonical,
                )

            # SymbolNormalizationError is raised before any I/O for invalid input
            try:
                normalize_symbol("AAPL")  # bare ticker, no default_exchange
            except SymbolNormalizationError as exc:
                logger.info("  SymbolNormalizationError raised before I/O: %s", exc)

        asyncio.run(_demo())

    # Confirm validate_symbols received only canonical forms
    calls = mock_validate.call_args_list
    canonical_args = [str(call.args[0]) for call in calls]
    assert all(arg == "NASDAQ:AAPL" for arg in canonical_args), (
        f"Expected all validate_symbols calls to receive 'NASDAQ:AAPL', got {canonical_args}"
    )
    logger.info("  All %d validate_symbols calls received canonical form ✓", len(calls))


if __name__ == "__main__":
    phase1_exchange_aware()
    phase1_detailed_result()
    phase1_batch()
    phase2_explicit_config()
    phase2_env_var()
    error_handling()
    phase3_ohlcv_integration_pattern()
