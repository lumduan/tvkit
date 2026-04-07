"""
Symbol normalization examples — tvkit.symbols.

Demonstrates Phase 1 (exchange-aware normalization) and Phase 2 (bare-ticker resolution
via NormalizationConfig and TVKIT_DEFAULT_EXCHANGE env var).

Run:
    uv run python examples/symbol_normalization_example.py
"""

import logging
import os

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


if __name__ == "__main__":
    phase1_exchange_aware()
    phase1_detailed_result()
    phase1_batch()
    phase2_explicit_config()
    phase2_env_var()
    error_handling()
