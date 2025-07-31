"""
TradingView Scanner Service.

This module provides a service for making requests to TradingView's scanner API
with proper error handling and response validation.
"""

import asyncio
import json
from typing import Any, Dict, Literal, Optional

import httpx
from pydantic import ValidationError

from tvkit.api.scanner.markets import Market, is_valid_market
from tvkit.api.scanner.models import ColumnSets, ScannerRequest, ScannerResponse


class ScannerServiceError(Exception):
    """Base exception for Scanner Service errors."""

    pass


class ScannerConnectionError(ScannerServiceError):
    """Raised when connection to scanner API fails."""

    pass


class ScannerAPIError(ScannerServiceError):
    """Raised when scanner API returns an error response."""

    pass


class ScannerValidationError(ScannerServiceError):
    """Raised when response validation fails."""

    pass


class ScannerService:
    """
    Service for interacting with TradingView's scanner API.

    This service handles POST requests to scanner endpoints with proper
    error handling, retry logic, and response validation.
    """

    def __init__(
        self,
        base_url: str = "https://scanner.tradingview.com",
        timeout: float = 30.0,
        max_retries: int = 3,
        user_agent: str = "tvkit/1.0",
    ) -> None:
        """
        Initialize the scanner service.

        Args:
            base_url: Base URL for the scanner API
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            user_agent: User agent string for requests

        Example:
            >>> service = ScannerService()
            >>> # Use default settings
        """
        self.base_url: str = base_url.rstrip("/")
        self.timeout: float = timeout
        self.max_retries: int = max_retries
        self.user_agent: str = user_agent

        # Default headers for requests
        self.headers: Dict[str, str] = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def scan_market(
        self,
        market: Market,
        request: ScannerRequest,
        label_product: str = "markets-screener",
    ) -> ScannerResponse:
        """
        Scan a specific market using the scanner API.

        Args:
            market: Market to scan (use Market enum)
            request: Scanner request configuration
            label_product: Label product parameter for the API

        Returns:
            Parsed scanner response with stock data

        Raises:
            ScannerConnectionError: If connection fails
            ScannerAPIError: If API returns an error
            ScannerValidationError: If response validation fails
            ValueError: If market is invalid

        Example:
            >>> from tvkit.api.scanner.models import create_scanner_request, ColumnSets
            >>> from tvkit.api.scanner.markets import Market
            >>> service = ScannerService()
            >>> request = create_scanner_request(
            ...     columns=ColumnSets.BASIC,
            ...     range_end=50
            ... )
            >>> response = await service.scan_market(Market.THAILAND, request)
            >>> print(f"Found {len(response.data)} stocks")

            Note: For comprehensive data with all available columns, use:
            >>> from tvkit.api.scanner.services import create_comprehensive_request
            >>> request = create_comprehensive_request()
            >>> response = await service.scan_market(Market.AMERICA, request)
        """
        endpoint: str = f"{self.base_url}/{market.value}/scan"
        params: Dict[str, str] = {"label-product": label_product}

        return await self._make_scanner_request(endpoint, request, params)

    async def scan_market_by_id(
        self,
        market_id: str,
        request: ScannerRequest,
        label_product: str = "markets-screener",
    ) -> ScannerResponse:
        """
        Scan a specific market using market identifier string.

        Args:
            market_id: Market identifier string (e.g., 'thailand', 'america', 'japan')
            request: Scanner request configuration
            label_product: Label product parameter for the API

        Returns:
            Parsed scanner response with stock data

        Raises:
            ScannerConnectionError: If connection fails
            ScannerAPIError: If API returns an error
            ScannerValidationError: If response validation fails
            ValueError: If market_id is invalid

        Example:
            >>> service = ScannerService()
            >>> request = create_scanner_request()
            >>> response = await service.scan_market_by_id("thailand", request)
        """
        if not is_valid_market(market_id):
            raise ValueError(f"Invalid market identifier: {market_id}")

        market: Market = Market(market_id)
        return await self.scan_market(market, request, label_product)

    async def _make_scanner_request(
        self,
        endpoint: str,
        request: ScannerRequest,
        params: Optional[Dict[str, str]] = None,
    ) -> ScannerResponse:
        """
        Make a scanner API request with retry logic.

        Args:
            endpoint: Full API endpoint URL
            request: Scanner request configuration
            params: URL parameters

        Returns:
            Parsed scanner response

        Raises:
            ScannerConnectionError: If connection fails after retries
            ScannerAPIError: If API returns an error
            ScannerValidationError: If response validation fails
        """
        # Convert request to JSON
        request_data: Dict[str, Any] = request.model_dump(by_alias=True)

        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        endpoint,
                        json=request_data,
                        headers=self.headers,
                        params=params or {},
                    )

                    # Check for HTTP errors
                    if response.status_code != 200:
                        error_text: str = response.text
                        raise ScannerAPIError(
                            f"Scanner API returned {response.status_code}: {error_text}"
                        )

                    # Parse JSON response
                    try:
                        response_data: Dict[str, Any] = response.json()
                    except json.JSONDecodeError as e:
                        raise ScannerAPIError(f"Invalid JSON response: {e}")

                    # Validate and parse response
                    try:
                        return ScannerResponse.from_api_response(
                            response_data, request.columns
                        )
                    except ValidationError as e:
                        raise ScannerValidationError(f"Response validation failed: {e}")

            except httpx.TimeoutException as e:
                last_exception = ScannerConnectionError(f"Request timeout: {e}")
            except httpx.ConnectError as e:
                last_exception = ScannerConnectionError(f"Connection error: {e}")
            except httpx.RequestError as e:
                last_exception = ScannerConnectionError(f"Request error: {e}")
            except (ScannerAPIError, ScannerValidationError):
                # These errors shouldn't be retried
                raise

            # Wait before retry (exponential backoff)
            if attempt < self.max_retries:
                wait_time: float = 2.0**attempt
                await asyncio.sleep(wait_time)

        # If we've exhausted all retries, raise the last exception
        if last_exception:
            raise last_exception
        else:
            raise ScannerConnectionError("Failed to connect after all retries")

    async def __aenter__(self) -> "ScannerService":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        # Suppress unused parameter warnings
        _ = exc_type, exc_val, exc_tb


def create_comprehensive_request(
    sort_by: str = "name",
    sort_order: Literal["asc", "desc"] = "asc",
    range_start: int = 0,
    range_end: int = 1000,
    language: str = "en",
) -> ScannerRequest:
    """
    Create a comprehensive scanner request with all available columns.

    This function uses the complete set of TradingView scanner columns
    for maximum data availability. For more focused requests, consider
    using create_scanner_request() with specific ColumnSets.

    Args:
        sort_by: Field to sort by (e.g., 'name', 'market_cap_basic', 'volume')
        sort_order: Sort order ('asc' or 'desc')
        range_start: Start index for results (0-based)
        range_end: End index for results (exclusive)
        language: Language code for response localization

    Returns:
        Configured ScannerRequest with comprehensive column set

    Raises:
        ValueError: If range parameters are invalid

    Example:
        >>> request = create_comprehensive_request(
        ...     sort_by="market_cap_basic",
        ...     sort_order="desc",
        ...     range_end=50
        ... )
        >>> service = ScannerService()
        >>> response = await service.scan_market(Market.THAILAND, request)
        >>> print(f"Retrieved {len(response.data)} stocks with full data")
    """
    from tvkit.api.scanner.models import ScannerOptions, ScannerRequest, SortConfig

    return ScannerRequest(
        columns=ColumnSets.COMPREHENSIVE_FULL,
        ignore_unknown_fields=False,
        options=ScannerOptions(lang=language),
        range=(range_start, range_end),
        sort=SortConfig(sortBy=sort_by, sortOrder=sort_order, nullsFirst=False),
        preset="all_stocks",
    )
