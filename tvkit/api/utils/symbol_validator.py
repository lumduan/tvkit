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
