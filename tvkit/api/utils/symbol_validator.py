"""
Symbol validation service for TradingView exchange symbols.

This module provides async functions for validating trading symbols against TradingView's
API to ensure they follow the correct format and exist in TradingView's system.
"""

import asyncio
import logging
from typing import List, Union

import httpx


async def validate_symbols(exchange_symbol: Union[str, List[str]]) -> bool:
    """
    Validate one or more exchange symbols asynchronously.

    This function checks whether the provided symbol or list of symbols follows
    the expected format ("EXCHANGE:SYMBOL") and validates each symbol by making a
    request to a TradingView validation URL.

    Args:
        exchange_symbol: A single symbol or a list of symbols in the format "EXCHANGE:SYMBOL".

    Raises:
        ValueError: If exchange_symbol is empty, if a symbol does not follow the "EXCHANGE:SYMBOL" format,
                    or if the symbol fails validation after the allowed number of retries.
        httpx.HTTPError: If there's an HTTP-related error during validation.

    Returns:
        True if all provided symbols are valid.

    Example:
        >>> await validate_symbols("BINANCE:BTCUSDT")
        True
        >>> await validate_symbols(["BINANCE:BTCUSDT", "NASDAQ:AAPL"])
        True
    """
    validate_url: str = (
        "https://scanner.tradingview.com/symbol?"
        "symbol={exchange}%3A{symbol}&fields=market&no_404=false"
    )

    if not exchange_symbol:
        raise ValueError("exchange_symbol cannot be empty")

    symbols: List[str]
    if isinstance(exchange_symbol, str):
        symbols = [exchange_symbol]
    else:
        symbols = exchange_symbol

    async with httpx.AsyncClient(timeout=5.0) as client:
        for item in symbols:
            parts: List[str] = item.split(":")
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid symbol format '{item}'. Must be like 'BINANCE:BTCUSDT'"
                )

            exchange: str
            symbol: str
            exchange, symbol = parts
            retries: int = 3

            for attempt in range(retries):
                try:
                    response: httpx.Response = await client.get(
                        url=validate_url.format(exchange=exchange, symbol=symbol)
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        raise ValueError(
                            f"Invalid exchange:symbol '{item}' after {retries} attempts"
                        ) from exc

                    logging.warning(
                        "Attempt %d failed to validate exchange:symbol '%s': %s",
                        attempt + 1,
                        item,
                        exc,
                    )

                    if attempt < retries - 1:
                        await asyncio.sleep(delay=1.0)  # Wait briefly before retrying
                    else:
                        raise ValueError(
                            f"Invalid exchange:symbol '{item}' after {retries} attempts"
                        ) from exc
                except httpx.RequestError as exc:
                    logging.warning(
                        "Attempt %d failed to validate exchange:symbol '%s': %s",
                        attempt + 1,
                        item,
                        exc,
                    )

                    if attempt < retries - 1:
                        await asyncio.sleep(delay=1.0)  # Wait briefly before retrying
                    else:
                        raise ValueError(
                            f"Invalid exchange:symbol '{item}' after {retries} attempts"
                        ) from exc
                else:
                    break  # Successful request; exit retry loop

    return True
