"""
Tests for tvkit.symbols Phase 2 — default exchange and env var support.

Coverage target: 100% line and branch for Phase 2 additions to tvkit/symbols/.

Test categories:
  - Bare-ticker resolution via explicit NormalizationConfig(default_exchange=...)
  - TVKIT_DEFAULT_EXCHANGE env var read by NormalizationConfig()
  - default_exchange=None with bare ticker still raises SymbolNormalizationError
  - NormalizationType.DEFAULT_EXCHANGE recorded in normalize_symbol_detailed result
  - normalize_symbols batch with default exchange
  - Exchange-aware symbols unaffected when default_exchange is set
  - Bare ticker lowercase resolution (uppercased after exchange prepend)
"""

import pytest
from pydantic import ValidationError

from tvkit.symbols import (
    NormalizationConfig,
    NormalizationType,
    SymbolNormalizationError,
    normalize_symbol,
    normalize_symbol_detailed,
    normalize_symbols,
)

# ---------------------------------------------------------------------------
# Bare-ticker resolution via explicit config
# ---------------------------------------------------------------------------


def test_bare_ticker_with_default_exchange() -> None:
    config = NormalizationConfig(default_exchange="NASDAQ")
    assert normalize_symbol("AAPL", config=config) == "NASDAQ:AAPL"


def test_bare_ticker_lowercase_with_default_exchange() -> None:
    # Ticker is uppercased after the exchange prefix is prepended
    config = NormalizationConfig(default_exchange="NASDAQ")
    assert normalize_symbol("aapl", config=config) == "NASDAQ:AAPL"


def test_bare_ticker_numeric_with_default_exchange() -> None:
    config = NormalizationConfig(default_exchange="HKEX")
    assert normalize_symbol("700", config=config) == "HKEX:700"


def test_bare_ticker_with_underscore_exchange() -> None:
    config = NormalizationConfig(default_exchange="FX_IDC")
    assert normalize_symbol("EURUSD", config=config) == "FX_IDC:EURUSD"


def test_bare_ticker_whitespace_stripped_then_resolved() -> None:
    # Whitespace is stripped first; bare ticker is then resolved via default exchange
    config = NormalizationConfig(default_exchange="NASDAQ")
    assert normalize_symbol("  AAPL  ", config=config) == "NASDAQ:AAPL"


# ---------------------------------------------------------------------------
# NormalizationType.DEFAULT_EXCHANGE
# ---------------------------------------------------------------------------


def test_normalize_symbol_detailed_default_exchange_type() -> None:
    config = NormalizationConfig(default_exchange="NASDAQ")
    result = normalize_symbol_detailed("AAPL", config=config)
    assert result.normalization_type == NormalizationType.DEFAULT_EXCHANGE
    assert result.canonical == "NASDAQ:AAPL"
    assert result.exchange == "NASDAQ"
    assert result.ticker == "AAPL"
    assert result.original == "AAPL"


def test_normalize_symbol_detailed_whitespace_takes_precedence_over_default_exchange() -> None:
    # Input has leading whitespace AND is a bare ticker: WHITESPACE_STRIP has higher priority
    config = NormalizationConfig(default_exchange="NASDAQ")
    result = normalize_symbol_detailed("  AAPL  ", config=config)
    assert result.normalization_type == NormalizationType.WHITESPACE_STRIP
    assert result.canonical == "NASDAQ:AAPL"


def test_normalize_symbol_detailed_default_exchange_lowercase_ticker() -> None:
    config = NormalizationConfig(default_exchange="NASDAQ")
    result = normalize_symbol_detailed("aapl", config=config)
    assert result.normalization_type == NormalizationType.DEFAULT_EXCHANGE
    assert result.canonical == "NASDAQ:AAPL"


# ---------------------------------------------------------------------------
# default_exchange=None still raises on bare tickers
# ---------------------------------------------------------------------------


def test_bare_ticker_no_config_still_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol("AAPL")
    assert "no exchange prefix" in exc_info.value.reason


def test_bare_ticker_default_exchange_none_raises() -> None:
    config = NormalizationConfig(default_exchange=None)
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol("AAPL", config=config)
    assert "no exchange prefix" in exc_info.value.reason


# ---------------------------------------------------------------------------
# Exchange-aware symbols unaffected when default_exchange is set
# ---------------------------------------------------------------------------


def test_exchange_aware_symbol_unaffected_by_default_exchange() -> None:
    config = NormalizationConfig(default_exchange="BINANCE")
    # A colon-prefixed symbol must NOT have its exchange overridden
    assert normalize_symbol("NASDAQ:AAPL", config=config) == "NASDAQ:AAPL"


def test_dash_notation_unaffected_by_default_exchange() -> None:
    config = NormalizationConfig(default_exchange="BINANCE")
    # Dash-notation is still an exchange-aware symbol — default exchange must NOT be applied
    assert normalize_symbol("NASDAQ-AAPL", config=config) == "NASDAQ:AAPL"


# ---------------------------------------------------------------------------
# normalize_symbols batch with default exchange
# ---------------------------------------------------------------------------


def test_normalize_symbols_batch_with_default_exchange() -> None:
    config = NormalizationConfig(default_exchange="NASDAQ")
    result = normalize_symbols(["AAPL", "MSFT", "GOOGL"], config=config)
    assert result == ["NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:GOOGL"]


def test_normalize_symbols_mixed_bare_and_exchange_aware() -> None:
    config = NormalizationConfig(default_exchange="NASDAQ")
    result = normalize_symbols(["AAPL", "BINANCE:BTCUSDT", "msft"], config=config)
    assert result == ["NASDAQ:AAPL", "BINANCE:BTCUSDT", "NASDAQ:MSFT"]


def test_normalize_symbols_batch_raises_on_invalid_with_default_exchange() -> None:
    config = NormalizationConfig(default_exchange="NASDAQ")
    with pytest.raises(SymbolNormalizationError):
        normalize_symbols(["AAPL", "INVALID SYMBOL"], config=config)


# ---------------------------------------------------------------------------
# TVKIT_DEFAULT_EXCHANGE env var support
# ---------------------------------------------------------------------------


def test_normalization_config_reads_default_exchange_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TVKIT_DEFAULT_EXCHANGE", "NASDAQ")
    config = NormalizationConfig()
    assert config.default_exchange == "NASDAQ"


def test_normalize_symbol_resolves_bare_ticker_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TVKIT_DEFAULT_EXCHANGE", "NYSE")
    config = NormalizationConfig()
    assert normalize_symbol("JPM", config=config) == "NYSE:JPM"


def test_normalization_config_env_var_absent_gives_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TVKIT_DEFAULT_EXCHANGE", raising=False)
    config = NormalizationConfig()
    assert config.default_exchange is None


def test_normalization_config_env_var_overridden_by_explicit_kwarg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TVKIT_DEFAULT_EXCHANGE", "NASDAQ")
    # Explicit kwarg takes precedence over env var
    config = NormalizationConfig(default_exchange="BINANCE")
    assert config.default_exchange == "BINANCE"


def test_normalization_config_invalid_env_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Lowercase exchange name is invalid — validator must reject it
    monkeypatch.setenv("TVKIT_DEFAULT_EXCHANGE", "nasdaq")
    with pytest.raises(ValidationError):
        NormalizationConfig()


# ---------------------------------------------------------------------------
# NormalizationConfig model — Phase 2 specific validators
# ---------------------------------------------------------------------------


def test_normalization_config_is_base_settings() -> None:
    from pydantic_settings import BaseSettings

    assert issubclass(NormalizationConfig, BaseSettings)


def test_normalization_config_env_prefix_is_tvkit() -> None:
    # Verify the env_prefix is set correctly by checking model_config
    assert NormalizationConfig.model_config.get("env_prefix") == "TVKIT_"
