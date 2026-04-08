"""
Integration tests for Phase 3: symbol normalization in tvkit.api.chart.ohlcv.

Verifies that:
  - All public OHLCV methods normalize before validating (normalize_symbol / normalize_symbols)
  - validate_symbols always receives a canonical EXCHANGE:SYMBOL string (or canonical list)
  - SymbolNormalizationError propagates immediately — before any I/O — for invalid symbols
  - convert_symbol_format emits DeprecationWarning (backward-compat check)
  - SymbolConversionResult is still importable and usable (backward-compat check)

External I/O (validate_symbols, WebSocket connections) is mocked throughout.
"""

from __future__ import annotations

import warnings
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tvkit.api.chart.ohlcv import OHLCV
from tvkit.symbols import SymbolNormalizationError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_connection_service() -> MagicMock:
    """Return a ConnectionService mock whose get_data_stream() is an empty async generator."""

    async def _empty_stream(*args: object, **kwargs: object) -> AsyncIterator[object]:
        return
        yield  # type: ignore[misc]  # makes the function an async generator

    svc = MagicMock()
    svc.get_data_stream = _empty_stream
    svc.close = AsyncMock()
    svc.initialize_sessions = AsyncMock()
    svc.add_multiple_symbols_to_sessions = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# Single-symbol methods: normalize_symbol called with raw input, validate gets canonical
# ---------------------------------------------------------------------------


class TestNormalizeBeforeValidate:
    """validate_symbols always receives the canonical form produced by normalize_symbol."""

    @pytest.mark.asyncio
    async def test_fetch_count_mode_passes_canonical_to_validate(self) -> None:
        """_fetch_count_mode: validate_symbols receives canonical NASDAQ:AAPL, not nasdaq:aapl."""
        client = OHLCV()
        client.connection_service = _mock_connection_service()

        with (
            patch.object(client, "_prepare_chart_session", new_callable=AsyncMock) as mock_prepare,
            patch(
                "tvkit.api.chart.ohlcv.validate_symbols", new_callable=AsyncMock
            ) as mock_validate,
            patch("tvkit.api.chart.ohlcv.validate_interval"),
        ):
            mock_validate.return_value = True

            # Raises RuntimeError at the end (no bars) — that's expected; we only care about
            # what was passed to validate_symbols and _prepare_chart_session.
            with pytest.raises(RuntimeError, match="No historical data"):
                await client._fetch_count_mode("nasdaq:aapl", "1D", bars_count=5)

            mock_validate.assert_called_once_with("NASDAQ:AAPL")
            mock_prepare.assert_called_once_with("NASDAQ:AAPL", "1D", 5, range_param="")

    @pytest.mark.asyncio
    async def test_fetch_count_mode_dash_notation_passed_canonical(self) -> None:
        """Dash-notation symbol NASDAQ-AAPL is normalized to NASDAQ:AAPL before validation."""
        client = OHLCV()
        client.connection_service = _mock_connection_service()

        with (
            patch.object(client, "_prepare_chart_session", new_callable=AsyncMock),
            patch(
                "tvkit.api.chart.ohlcv.validate_symbols", new_callable=AsyncMock
            ) as mock_validate,
            patch("tvkit.api.chart.ohlcv.validate_interval"),
        ):
            mock_validate.return_value = True

            with pytest.raises(RuntimeError, match="No historical data"):
                await client._fetch_count_mode("NASDAQ-AAPL", "1D", bars_count=5)

            mock_validate.assert_called_once_with("NASDAQ:AAPL")

    @pytest.mark.asyncio
    async def test_normalize_symbol_called_before_validate(self) -> None:
        """normalize_symbol is invoked before validate_symbols — strict ordering check."""
        client = OHLCV()
        client.connection_service = _mock_connection_service()

        call_order: list[str] = []

        def _track_normalize(sym: str) -> str:
            call_order.append("normalize")
            from tvkit.symbols import normalize_symbol as _real

            return _real(sym)

        async def _track_validate(sym: str | list[str]) -> bool:
            call_order.append("validate")
            return True

        with (
            patch.object(client, "_prepare_chart_session", new_callable=AsyncMock),
            patch("tvkit.api.chart.ohlcv.normalize_symbol", side_effect=_track_normalize),
            patch("tvkit.api.chart.ohlcv.validate_symbols", side_effect=_track_validate),
            patch("tvkit.api.chart.ohlcv.validate_interval"),
        ):
            with pytest.raises(RuntimeError, match="No historical data"):
                await client._fetch_count_mode("NASDAQ:AAPL", "1D", bars_count=5)

        assert call_order == ["normalize", "validate"], (
            f"Expected normalize before validate, got: {call_order}"
        )


# ---------------------------------------------------------------------------
# Multi-symbol path: get_latest_trade_info
# ---------------------------------------------------------------------------


class TestMultiSymbolNormalization:
    """normalize_symbols runs before validate_symbols for get_latest_trade_info."""

    @pytest.mark.asyncio
    async def test_get_latest_trade_info_normalizes_batch_before_validate(self) -> None:
        """normalize_symbols is called first; validate_symbols receives the canonical list."""
        client = OHLCV()
        client.connection_service = _mock_connection_service()
        client.message_service = MagicMock()
        client.message_service.generate_session = MagicMock(side_effect=["qs_1", "cs_1"])
        client.message_service.get_send_message_callable = MagicMock(return_value=AsyncMock())

        call_order: list[str] = []
        captured_validate_arg: list[object] = []

        def _track_normalize(syms: list[str]) -> list[str]:
            call_order.append("normalize_symbols")
            return ["NASDAQ:AAPL", "BINANCE:BTCUSDT"]

        async def _track_validate(sym: str | list[str]) -> bool:
            call_order.append("validate_symbols")
            captured_validate_arg.append(sym)
            return True

        with (
            patch.object(client, "_setup_services", new_callable=AsyncMock),
            patch("tvkit.api.chart.ohlcv.normalize_symbols", side_effect=_track_normalize),
            patch("tvkit.api.chart.ohlcv.validate_symbols", side_effect=_track_validate),
        ):
            # Consume the generator fully (empty stream, so no items)
            async for _ in client.get_latest_trade_info(["nasdaq:aapl", "binance:btcusdt"]):
                pass

        assert call_order == ["normalize_symbols", "validate_symbols"], (
            f"Expected normalize_symbols before validate_symbols, got: {call_order}"
        )
        assert captured_validate_arg[0] == ["NASDAQ:AAPL", "BINANCE:BTCUSDT"]


# ---------------------------------------------------------------------------
# SymbolNormalizationError propagates before I/O
# ---------------------------------------------------------------------------


class TestSymbolNormalizationErrorPropagates:
    """SymbolNormalizationError is raised before any I/O for invalid / ambiguous symbols."""

    @pytest.mark.asyncio
    async def test_bare_ticker_raises_before_validate(self) -> None:
        """A bare ticker with no default_exchange raises SymbolNormalizationError before validate."""
        client = OHLCV()
        client.connection_service = _mock_connection_service()

        with (
            patch.object(client, "_prepare_chart_session", new_callable=AsyncMock),
            patch(
                "tvkit.api.chart.ohlcv.validate_symbols", new_callable=AsyncMock
            ) as mock_validate,
            patch("tvkit.api.chart.ohlcv.validate_interval"),
        ):
            with pytest.raises(SymbolNormalizationError, match="no exchange prefix"):
                await client._fetch_count_mode("AAPL", "1D", bars_count=10)

            mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_symbol_raises_before_validate(self) -> None:
        """An empty string raises SymbolNormalizationError before validate_symbols."""
        client = OHLCV()
        client.connection_service = _mock_connection_service()

        with (
            patch.object(client, "_prepare_chart_session", new_callable=AsyncMock),
            patch(
                "tvkit.api.chart.ohlcv.validate_symbols", new_callable=AsyncMock
            ) as mock_validate,
            patch("tvkit.api.chart.ohlcv.validate_interval"),
        ):
            with pytest.raises(SymbolNormalizationError, match="must not be empty"):
                await client._fetch_count_mode("", "1D", bars_count=10)

            mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_string_symbol_raises_before_validate(self) -> None:
        """A non-string input raises SymbolNormalizationError before validate_symbols."""
        client = OHLCV()
        client.connection_service = _mock_connection_service()

        with (
            patch.object(client, "_prepare_chart_session", new_callable=AsyncMock),
            patch(
                "tvkit.api.chart.ohlcv.validate_symbols", new_callable=AsyncMock
            ) as mock_validate,
            patch("tvkit.api.chart.ohlcv.validate_interval"),
        ):
            with pytest.raises(SymbolNormalizationError, match="must be a str"):
                await client._fetch_count_mode(123, "1D", bars_count=10)  # type: ignore[arg-type]

            mock_validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_symbol_with_internal_whitespace_raises_before_validate(self) -> None:
        """A symbol with internal whitespace raises SymbolNormalizationError before validate."""
        client = OHLCV()
        client.connection_service = _mock_connection_service()

        with (
            patch.object(client, "_prepare_chart_session", new_callable=AsyncMock),
            patch(
                "tvkit.api.chart.ohlcv.validate_symbols", new_callable=AsyncMock
            ) as mock_validate,
            patch("tvkit.api.chart.ohlcv.validate_interval"),
        ):
            with pytest.raises(SymbolNormalizationError, match="internal whitespace"):
                await client._fetch_count_mode("NASDAQ AAPL", "1D", bars_count=10)

            mock_validate.assert_not_called()


# ---------------------------------------------------------------------------
# Deprecation warnings and backward compatibility
# ---------------------------------------------------------------------------


class TestDeprecationAndBackwardCompat:
    """convert_symbol_format emits DeprecationWarning; imports remain intact."""

    def test_convert_symbol_format_emits_deprecation_warning_for_dash_symbol(self) -> None:
        from tvkit.api.utils import convert_symbol_format

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = convert_symbol_format("NASDAQ-AAPL")

        deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecation_warnings, "Expected DeprecationWarning from convert_symbol_format"
        assert "normalize_symbol" in str(deprecation_warnings[0].message)
        assert result.converted_symbol == "NASDAQ:AAPL"
        assert result.is_converted is True

    def test_convert_symbol_format_emits_deprecation_warning_for_colon_symbol(self) -> None:
        from tvkit.api.utils import convert_symbol_format

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = convert_symbol_format("NASDAQ:AAPL")

        deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecation_warnings
        assert result.converted_symbol == "NASDAQ:AAPL"
        assert result.is_converted is False

    def test_convert_symbol_format_list_emits_deprecation_warning(self) -> None:
        from tvkit.api.utils import convert_symbol_format

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            results = convert_symbol_format(["NASDAQ-AAPL", "BINANCE:BTCUSDT"])

        deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecation_warnings
        assert isinstance(results, list)
        assert results[0].converted_symbol == "NASDAQ:AAPL"
        assert results[1].converted_symbol == "BINANCE:BTCUSDT"

    def test_symbol_conversion_result_still_importable_and_usable(self) -> None:
        from tvkit.api.utils import SymbolConversionResult

        result = SymbolConversionResult(
            original_symbol="NASDAQ-AAPL",
            converted_symbol="NASDAQ:AAPL",
            is_converted=True,
        )
        assert result.original_symbol == "NASDAQ-AAPL"
        assert result.converted_symbol == "NASDAQ:AAPL"
        assert result.is_converted is True

    def test_symbol_conversion_result_docstring_contains_deprecation_notice(self) -> None:
        from tvkit.api.utils import SymbolConversionResult

        assert "deprecated" in (SymbolConversionResult.__doc__ or "").lower()
        assert "NormalizedSymbol" in (SymbolConversionResult.__doc__ or "")
