"""
Symbol validation service for TradingView exchange symbols.

This module provides async functions for validating trading symbols against TradingView's
API to ensure they follow the correct format and exist in TradingView's system.
"""

import asyncio
import logging
from typing import List, Union

import httpx

from .models import SymbolConversionResult


async def validate_symbols(exchange_symbol: Union[str, List[str]]) -> bool:
    """
    Validate one or more exchange symbols asynchronously.

    This function validates trading symbols by making requests to TradingView's
    symbol URL endpoint. Symbols can be in various formats including "EXCHANGE:SYMBOL"
    format or other TradingView-compatible formats like "USI-PCC".

    Args:
        exchange_symbol: A single symbol or a list of symbols to validate.
                        Supports formats like "BINANCE:BTCUSDT", "USI-PCC", etc.

    Raises:
        ValueError: If exchange_symbol is empty or if the symbol fails validation
                    after the allowed number of retries.
        httpx.HTTPError: If there's an HTTP-related error during validation.

    Returns:
        True if all provided symbols are valid.

    Example:
        >>> await validate_symbols("BINANCE:BTCUSDT")
        True
        >>> await validate_symbols(["BINANCE:BTCUSDT", "USI-PCC"])
        True
        >>> await validate_symbols("NASDAQ:AAPL")
        True
    """
    validate_url: str = "https://www.tradingview.com/symbols/{exchange_symbol}"

    if not exchange_symbol:
        raise ValueError("exchange_symbol cannot be empty")

    symbols: List[str]
    if isinstance(exchange_symbol, str):
        symbols = [exchange_symbol]
    else:
        symbols = exchange_symbol

    async with httpx.AsyncClient(timeout=5.0) as client:
        for item in symbols:
            retries: int = 3

            for attempt in range(retries):
                try:
                    response: httpx.Response = await client.get(
                        url=validate_url.format(exchange_symbol=item)
                    )

                    # Consider both 200 and 301 status codes as valid
                    if response.status_code in [200, 301]:
                        break  # Valid symbol, exit retry loop
                    elif response.status_code == 404:
                        raise ValueError(
                            f"Invalid exchange or symbol or index '{item}'"
                        )
                    else:
                        response.raise_for_status()

                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        raise ValueError(
                            f"Invalid exchange or symbol or index '{item}'"
                        ) from exc

                    logging.warning(
                        "Attempt %d failed to validate symbol '%s': %s",
                        attempt + 1,
                        item,
                        exc,
                    )

                    if attempt < retries - 1:
                        await asyncio.sleep(delay=1.0)  # Wait briefly before retrying
                    else:
                        raise ValueError(
                            f"Invalid symbol '{item}' after {retries} attempts"
                        ) from exc
                except httpx.RequestError as exc:
                    logging.warning(
                        "Attempt %d failed to validate symbol '%s': %s",
                        attempt + 1,
                        item,
                        exc,
                    )

                    if attempt < retries - 1:
                        await asyncio.sleep(delay=1.0)  # Wait briefly before retrying
                    else:
                        raise ValueError(
                            f"Invalid symbol '{item}' after {retries} attempts"
                        ) from exc

    return True


def convert_symbol_format(
    exchange_symbol: Union[str, List[str]],
) -> Union[SymbolConversionResult, List[SymbolConversionResult]]:
    """
    Convert exchange symbols from EXCHANGE-SYMBOL to EXCHANGE:SYMBOL format.

    This function converts trading symbols from the dash-separated format (e.g., "USI-PCC")
    to the colon-separated format (e.g., "USI:PCC") that is commonly used in TradingView.
    Symbols already in colon format are returned unchanged.

    Args:
        exchange_symbol: A single symbol or a list of symbols to convert.
                        Supports formats like "USI-PCC", "NASDAQ-AAPL", etc.

    Returns:
        SymbolConversionResult or List[SymbolConversionResult]: Conversion results containing
        original symbol, converted symbol, and conversion status.

    Raises:
        ValueError: If exchange_symbol is empty.

    Example:
        >>> result = convert_symbol_format("USI-PCC")
        >>> print(result.converted_symbol)
        'USI:PCC'
        >>> print(result.is_converted)
        True
        >>>
        >>> results = convert_symbol_format(["USI-PCC", "NASDAQ:AAPL"])
        >>> print(results[0].converted_symbol)  # "USI:PCC"
        >>> print(results[1].converted_symbol)  # "NASDAQ:AAPL"
        >>> print(results[1].is_converted)      # False (already in correct format)
    """
    if not exchange_symbol:
        raise ValueError("exchange_symbol cannot be empty")

    def _convert_single_symbol(symbol: str) -> SymbolConversionResult:
        """Convert a single symbol from dash to colon format."""
        if not symbol:
            raise ValueError("Symbol cannot be empty")

        # Check if symbol already contains colon (correct format)
        if ":" in symbol:
            return SymbolConversionResult(
                original_symbol=symbol, converted_symbol=symbol, is_converted=False
            )

        # Check if symbol contains dash (needs conversion)
        if "-" in symbol:
            converted: str = symbol.replace("-", ":", 1)  # Replace only first dash
            return SymbolConversionResult(
                original_symbol=symbol, converted_symbol=converted, is_converted=True
            )

        # Symbol doesn't contain dash or colon, return as-is
        return SymbolConversionResult(
            original_symbol=symbol, converted_symbol=symbol, is_converted=False
        )

    if isinstance(exchange_symbol, str):
        return _convert_single_symbol(exchange_symbol)
    else:
        return [_convert_single_symbol(symbol) for symbol in exchange_symbol]
