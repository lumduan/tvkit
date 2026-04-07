"""
Tests for tvkit.symbols — canonical symbol normalization layer (Phase 1).

Coverage target: 100% line and branch for tvkit/symbols/.

Test categories:
  - Happy path: all Phase 1 normalization variants
  - Edge cases: single-char ticker, numeric ticker, long exchange, FX_IDC, NYSE:BRK.B,
                combined transforms, duplicate inputs
  - Error conditions: empty, whitespace-only, bare ticker, multiple colons,
                      internal whitespace, empty components, special characters,
                      non-str inputs
  - normalize_symbols batch: order preservation, 1:1 no-dedup, raises on first invalid,
                              non-list input
  - normalize_symbol_detailed: NormalizationType for each variant, field assertions
  - NormalizationConfig: default_exchange validator, frozen model
  - NormalizedSymbol: validator contract, canonical == exchange:ticker
"""

import pytest
from pydantic import ValidationError

from tvkit.symbols import (
    NormalizationConfig,
    NormalizationType,
    NormalizedSymbol,
    SymbolNormalizationError,
    normalize_symbol,
    normalize_symbol_detailed,
    normalize_symbols,
)

# ---------------------------------------------------------------------------
# Happy path — parametrized normalization variants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "input_sym, expected",
    [
        # Already canonical
        ("NASDAQ:AAPL", "NASDAQ:AAPL"),
        ("BINANCE:BTCUSDT", "BINANCE:BTCUSDT"),
        ("NYSE:JPM", "NYSE:JPM"),
        # Lowercase only
        ("nasdaq:aapl", "NASDAQ:AAPL"),
        ("binance:btcusdt", "BINANCE:BTCUSDT"),
        # Dash notation
        ("NASDAQ-AAPL", "NASDAQ:AAPL"),
        ("BINANCE-BTCUSDT", "BINANCE:BTCUSDT"),
        # Dash + lowercase
        ("nasdaq-aapl", "NASDAQ:AAPL"),
        # Whitespace padding
        ("  NASDAQ:AAPL  ", "NASDAQ:AAPL"),
        ("\tNASDAQ:AAPL\n", "NASDAQ:AAPL"),
        # Exchange with underscore (e.g. FX_IDC, CME_MINI)
        ("FX_IDC:EURUSD", "FX_IDC:EURUSD"),
        ("fx_idc:eurusd", "FX_IDC:EURUSD"),
        ("CME_MINI:ES1!", "CME_MINI:ES1!"),
        # Ticker with dot (e.g. BRK.B)
        ("NYSE:BRK.B", "NYSE:BRK.B"),
        ("nyse:brk.b", "NYSE:BRK.B"),
        # Index / macro symbols
        ("INDEX:NDFI", "INDEX:NDFI"),
        ("USI:PCC", "USI:PCC"),
        ("FOREXCOM:EURUSD", "FOREXCOM:EURUSD"),
        # Single-character ticker
        ("NYSE:A", "NYSE:A"),
        # Numeric ticker
        ("HKEX:700", "HKEX:700"),
    ],
)
def test_normalize_symbol_happy_path(input_sym: str, expected: str) -> None:
    assert normalize_symbol(input_sym) == expected


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_normalize_symbol_single_character_ticker() -> None:
    assert normalize_symbol("NYSE:A") == "NYSE:A"


def test_normalize_symbol_numeric_ticker() -> None:
    assert normalize_symbol("HKEX:700") == "HKEX:700"


def test_normalize_symbol_long_exchange_name() -> None:
    assert normalize_symbol("FOREXCOM:EURUSD") == "FOREXCOM:EURUSD"


def test_normalize_symbol_exchange_with_underscore() -> None:
    assert normalize_symbol("FX_IDC:EURUSD") == "FX_IDC:EURUSD"


def test_normalize_symbol_ticker_with_dot() -> None:
    assert normalize_symbol("NYSE:BRK.B") == "NYSE:BRK.B"


def test_normalize_symbol_ticker_with_exclamation() -> None:
    # Continuous futures: ES1!, NQ1!
    assert normalize_symbol("CME_MINI:ES1!") == "CME_MINI:ES1!"


def test_normalize_symbol_combined_whitespace_lowercase_dash() -> None:
    # All three transforms in one input
    assert normalize_symbol("  nasdaq-aapl  ") == "NASDAQ:AAPL"


def test_normalize_symbols_empty_list_returns_empty() -> None:
    assert normalize_symbols([]) == []


def test_normalize_symbols_preserves_input_order() -> None:
    inputs = ["BINANCE:BTCUSDT", "NASDAQ:AAPL", "NYSE:JPM"]
    result = normalize_symbols(inputs)
    assert result == ["BINANCE:BTCUSDT", "NASDAQ:AAPL", "NYSE:JPM"]


def test_normalize_symbols_one_to_one_no_dedup() -> None:
    # Duplicate inputs must produce duplicate outputs — no deduplication
    result = normalize_symbols(["NASDAQ:AAPL", "nasdaq:aapl", "NASDAQ:AAPL"])
    assert result == ["NASDAQ:AAPL", "NASDAQ:AAPL", "NASDAQ:AAPL"]


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------


def test_normalize_symbol_empty_string_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol("")
    assert exc_info.value.original == ""
    assert "empty" in exc_info.value.reason


def test_normalize_symbol_whitespace_only_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol("   ")
    assert "empty" in exc_info.value.reason


def test_normalize_symbol_bare_ticker_no_config_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol("AAPL")
    assert exc_info.value.original == "AAPL"
    assert "no exchange prefix" in exc_info.value.reason


def test_normalize_symbol_multiple_colons_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol("A:B:C")
    assert "multiple" in exc_info.value.reason.lower()


def test_normalize_symbol_internal_whitespace_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol("INVALID SYMBOL")
    assert "whitespace" in exc_info.value.reason


def test_normalize_symbol_empty_exchange_component_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol(":AAPL")
    assert "exchange" in exc_info.value.reason


def test_normalize_symbol_empty_ticker_component_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol("NASDAQ:")
    assert "ticker" in exc_info.value.reason


def test_normalize_symbol_special_characters_raises() -> None:
    with pytest.raises(SymbolNormalizationError):
        normalize_symbol("NASDAQ:AAPL@")


def test_normalize_symbol_slash_pair_raises() -> None:
    # BTC/USDT is out of scope in Phase 1
    with pytest.raises(SymbolNormalizationError):
        normalize_symbol("BTC/USDT")


def test_normalize_symbol_non_str_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol(None)  # type: ignore[arg-type]
    assert "str" in exc_info.value.reason


def test_normalize_symbol_int_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol(123)  # type: ignore[arg-type]
    assert "str" in exc_info.value.reason


# ---------------------------------------------------------------------------
# Leading/trailing whitespace with strip_whitespace=False
# ---------------------------------------------------------------------------


def test_normalize_symbol_strip_whitespace_false_raises_on_padded_input() -> None:
    config = NormalizationConfig(strip_whitespace=False)
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol("  NASDAQ:AAPL  ", config=config)
    # Should mention leading/trailing whitespace, not "internal whitespace"
    assert "leading or trailing" in exc_info.value.reason


def test_normalize_symbol_strip_whitespace_false_accepts_clean_input() -> None:
    config = NormalizationConfig(strip_whitespace=False)
    assert normalize_symbol("NASDAQ:AAPL", config=config) == "NASDAQ:AAPL"


# ---------------------------------------------------------------------------
# normalize_symbols batch — error paths
# ---------------------------------------------------------------------------


def test_normalize_symbols_raises_on_first_invalid() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbols(["NASDAQ:AAPL", "INVALID"])
    # The error must be about the second (invalid) symbol
    assert exc_info.value.original == "INVALID"


def test_normalize_symbols_non_list_str_raises() -> None:
    # Passing a plain str should raise, not silently iterate characters
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbols("NASDAQ:AAPL")  # type: ignore[arg-type]
    assert "list" in exc_info.value.reason


def test_normalize_symbols_non_list_none_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbols(None)  # type: ignore[arg-type]
    assert "list" in exc_info.value.reason


def test_normalize_symbols_non_str_element_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbols(["NASDAQ:AAPL", 42])  # type: ignore[list-item]
    assert "str" in exc_info.value.reason


# ---------------------------------------------------------------------------
# normalize_symbol_detailed — NormalizationType per variant
# ---------------------------------------------------------------------------


def test_normalize_symbol_detailed_already_canonical() -> None:
    result = normalize_symbol_detailed("NASDAQ:AAPL")
    assert result.normalization_type == NormalizationType.ALREADY_CANONICAL
    assert result.canonical == "NASDAQ:AAPL"
    assert result.original == "NASDAQ:AAPL"


def test_normalize_symbol_detailed_uppercase_only() -> None:
    result = normalize_symbol_detailed("nasdaq:aapl")
    assert result.normalization_type == NormalizationType.UPPERCASE_ONLY
    assert result.canonical == "NASDAQ:AAPL"
    assert result.original == "nasdaq:aapl"


def test_normalize_symbol_detailed_dash_to_colon() -> None:
    result = normalize_symbol_detailed("NASDAQ-AAPL")
    assert result.normalization_type == NormalizationType.DASH_TO_COLON
    assert result.canonical == "NASDAQ:AAPL"
    assert result.original == "NASDAQ-AAPL"


def test_normalize_symbol_detailed_whitespace_strip() -> None:
    result = normalize_symbol_detailed("  NASDAQ:AAPL  ")
    assert result.normalization_type == NormalizationType.WHITESPACE_STRIP
    assert result.canonical == "NASDAQ:AAPL"
    assert result.original == "  NASDAQ:AAPL  "


def test_normalize_symbol_detailed_whitespace_strip_takes_precedence() -> None:
    # Whitespace + dash + lowercase → primary type is WHITESPACE_STRIP
    result = normalize_symbol_detailed("  nasdaq-aapl  ")
    assert result.normalization_type == NormalizationType.WHITESPACE_STRIP


def test_normalize_symbol_detailed_exchange_ticker_split() -> None:
    result = normalize_symbol_detailed("BINANCE:BTCUSDT")
    assert result.exchange == "BINANCE"
    assert result.ticker == "BTCUSDT"


def test_normalize_symbol_detailed_exchange_underscore() -> None:
    result = normalize_symbol_detailed("FX_IDC:EURUSD")
    assert result.exchange == "FX_IDC"
    assert result.ticker == "EURUSD"


def test_normalize_symbol_detailed_ticker_dot() -> None:
    result = normalize_symbol_detailed("NYSE:BRK.B")
    assert result.exchange == "NYSE"
    assert result.ticker == "BRK.B"


def test_normalize_symbol_detailed_ticker_exclamation() -> None:
    result = normalize_symbol_detailed("CME_MINI:ES1!")
    assert result.exchange == "CME_MINI"
    assert result.ticker == "ES1!"


def test_normalize_symbol_detailed_non_str_raises() -> None:
    with pytest.raises(SymbolNormalizationError) as exc_info:
        normalize_symbol_detailed(None)  # type: ignore[arg-type]
    assert "str" in exc_info.value.reason


# ---------------------------------------------------------------------------
# NormalizationConfig validator
# ---------------------------------------------------------------------------


def test_normalization_config_default_exchange_none_is_valid() -> None:
    config = NormalizationConfig()
    assert config.default_exchange is None
    assert config.strip_whitespace is True


def test_normalization_config_explicit_none_is_valid() -> None:
    # Exercises the validator's early-return branch for None
    config = NormalizationConfig(default_exchange=None)
    assert config.default_exchange is None


def test_normalization_config_valid_default_exchange() -> None:
    config = NormalizationConfig(default_exchange="NASDAQ")
    assert config.default_exchange == "NASDAQ"


def test_normalization_config_default_exchange_with_underscore() -> None:
    config = NormalizationConfig(default_exchange="FX_IDC")
    assert config.default_exchange == "FX_IDC"


def test_normalization_config_default_exchange_strips_surrounding_whitespace() -> None:
    config = NormalizationConfig(default_exchange="  NASDAQ  ")
    assert config.default_exchange == "NASDAQ"


def test_normalization_config_default_exchange_empty_raises() -> None:
    with pytest.raises(ValidationError):
        NormalizationConfig(default_exchange="")


def test_normalization_config_default_exchange_whitespace_only_raises() -> None:
    with pytest.raises(ValidationError):
        NormalizationConfig(default_exchange="   ")


def test_normalization_config_default_exchange_lowercase_raises() -> None:
    with pytest.raises(ValidationError):
        NormalizationConfig(default_exchange="nasdaq")


def test_normalization_config_is_frozen() -> None:
    config = NormalizationConfig()
    with pytest.raises(ValidationError):
        config.strip_whitespace = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# NormalizedSymbol validator contract
# ---------------------------------------------------------------------------


def test_normalized_symbol_valid_construction() -> None:
    model = NormalizedSymbol(
        canonical="NASDAQ:AAPL",
        exchange="NASDAQ",
        ticker="AAPL",
        original="nasdaq:aapl",
        normalization_type=NormalizationType.UPPERCASE_ONLY,
    )
    assert model.canonical == "NASDAQ:AAPL"


def test_normalized_symbol_canonical_must_match_exchange_colon_ticker() -> None:
    with pytest.raises(ValidationError):
        NormalizedSymbol(
            canonical="NASDAQ:MSFT",  # mismatch
            exchange="NASDAQ",
            ticker="AAPL",
            original="NASDAQ:AAPL",
            normalization_type=NormalizationType.ALREADY_CANONICAL,
        )


def test_normalized_symbol_empty_exchange_raises() -> None:
    with pytest.raises(ValidationError):
        NormalizedSymbol(
            canonical=":AAPL",
            exchange="",
            ticker="AAPL",
            original=":AAPL",
            normalization_type=NormalizationType.ALREADY_CANONICAL,
        )


def test_normalized_symbol_whitespace_only_original_raises() -> None:
    with pytest.raises(ValidationError):
        NormalizedSymbol(
            canonical="NASDAQ:AAPL",
            exchange="NASDAQ",
            ticker="AAPL",
            original="   ",
            normalization_type=NormalizationType.WHITESPACE_STRIP,
        )


def test_normalized_symbol_is_frozen() -> None:
    model = NormalizedSymbol(
        canonical="NASDAQ:AAPL",
        exchange="NASDAQ",
        ticker="AAPL",
        original="NASDAQ:AAPL",
        normalization_type=NormalizationType.ALREADY_CANONICAL,
    )
    with pytest.raises(ValidationError):
        model.canonical = "BINANCE:BTCUSDT"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SymbolNormalizationError attributes
# ---------------------------------------------------------------------------


def test_symbol_normalization_error_attributes() -> None:
    exc = SymbolNormalizationError(original="AAPL", reason="no exchange prefix")
    assert exc.original == "AAPL"
    assert exc.reason == "no exchange prefix"
    assert str(exc) == "Cannot normalize 'AAPL': no exchange prefix"


def test_symbol_normalization_error_is_value_error() -> None:
    exc = SymbolNormalizationError(original="x", reason="test")
    assert isinstance(exc, ValueError)
