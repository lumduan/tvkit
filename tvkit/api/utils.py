"""
Module providing utility functions for validating exchange symbols and fetching
TradingView indicators and their metadata.

This module contains async functions to:
  - Validate one or more exchange symbols.
  - Fetch a list of TradingView indicators based on a search query.
  - Display the fetched indicators and allow the user to select one.
  - Fetch and prepare indicator metadata for further processing.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from pydantic import BaseModel, Field


def convert_timestamp_to_iso(timestamp: float) -> str:
    """
    Convert a Unix timestamp to ISO 8601 format string.

    This function converts TradingView timestamps (Unix epoch seconds)
    to human-readable ISO 8601 format with UTC timezone.

    Args:
        timestamp: Unix timestamp as a float (seconds since epoch).

    Returns:
        ISO 8601 formatted datetime string with UTC timezone.

    Example:
        >>> convert_timestamp_to_iso(1753436820.0)
        '2025-07-28T12:13:40+00:00'
        >>> convert_timestamp_to_iso(1640995200.0)
        '2022-01-01T00:00:00+00:00'
    """
    dt: datetime = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.isoformat()


class IndicatorData(BaseModel):
    """Data structure for TradingView indicator information."""

    script_name: str = Field(..., description="Name of the indicator script")
    image_url: str = Field(..., description="URL of the indicator image")
    author: str = Field(..., description="Author username")
    agree_count: int = Field(..., ge=0, description="Number of agree votes")
    is_recommended: bool = Field(
        ..., description="Whether the indicator is recommended"
    )
    script_id_part: str = Field(..., description="Script ID part for the indicator")
    version: Optional[str] = Field(None, description="Version of the indicator script")

    model_config = {"frozen": True}  # Make the model immutable

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "scriptName": self.script_name,
            "imageUrl": self.image_url,
            "author": self.author,
            "agreeCount": self.agree_count,
            "isRecommended": self.is_recommended,
            "scriptIdPart": self.script_id_part,
            "version": self.version,
        }


class PineFeatures(BaseModel):
    """Pydantic model for Pine script features configuration."""

    v: str = Field(..., description="Pine features JSON string")
    f: bool = Field(True, description="Features flag")
    t: str = Field("text", description="Type identifier")

    model_config = {"frozen": True}


class ProfileConfig(BaseModel):
    """Pydantic model for profile configuration."""

    v: bool = Field(False, description="Profile value")
    f: bool = Field(True, description="Profile flag")
    t: str = Field("bool", description="Type identifier")

    model_config = {"frozen": True}


class InputValue(BaseModel):
    """Pydantic model for input value configuration."""

    v: Any = Field(..., description="Input value")
    f: bool = Field(True, description="Input flag")
    t: str = Field(..., description="Input type")

    model_config = {"frozen": True}


class StudyPayload(BaseModel):
    """Pydantic model for study creation payload."""

    m: str = Field("create_study", description="Method name")
    p: List[Any] = Field(..., description="Parameters list")

    model_config = {"frozen": True}


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


async def fetch_tradingview_indicators(query: str) -> List[IndicatorData]:
    """
    Fetch TradingView indicators based on a search query asynchronously.

    This function sends a GET request to the TradingView public endpoint for indicator
    suggestions and filters the results by checking if the search query appears in either
    the script name or the author's username.

    Args:
        query: The search term used to filter indicators by script name or author.

    Returns:
        A list of IndicatorData objects containing details of matching indicators.

    Raises:
        httpx.HTTPError: If there's an HTTP-related error during the request.

    Example:
        >>> indicators = await fetch_tradingview_indicators("RSI")
        >>> for indicator in indicators:
        ...     print(f"{indicator.script_name} by {indicator.author}")
    """
    url: str = f"https://www.tradingview.com/pubscripts-suggest-json/?search={query}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response: httpx.Response = await client.get(url=url)
            response.raise_for_status()
            json_data: Dict[str, Any] = response.json()

            results: List[Any] = json_data.get("results", [])
            filtered_results: List[IndicatorData] = []

            for indicator in results:
                if (
                    query.lower() in indicator["scriptName"].lower()
                    or query.lower() in indicator["author"]["username"].lower()
                ):
                    filtered_results.append(
                        IndicatorData(
                            script_name=indicator["scriptName"],
                            image_url=indicator["imageUrl"],
                            author=indicator["author"]["username"],
                            agree_count=indicator["agreeCount"],
                            is_recommended=indicator["isRecommended"],
                            script_id_part=indicator["scriptIdPart"],
                            version=indicator.get("version"),
                        )
                    )

            return filtered_results

    except httpx.RequestError as exc:
        logging.error("Error fetching TradingView indicators: %s", exc)
        return []


def display_and_select_indicator(
    indicators: List[IndicatorData],
) -> Optional[Tuple[Optional[str], Optional[str]]]:
    """
    Display a list of indicators and prompt the user to select one.

    This function prints the available indicators with numbering, waits for the user
    to input the number corresponding to their preferred indicator, and returns the
    selected indicator's scriptId and version.

    Args:
        indicators: A list of IndicatorData objects containing indicator details.

    Returns:
        A tuple (scriptId, version) of the selected indicator if the selection
        is valid; otherwise, None.

    Example:
        >>> indicators = await fetch_tradingview_indicators("RSI")
        >>> result = display_and_select_indicator(indicators)
        >>> if result:
        ...     script_id, version = result
        ...     print(f"Selected script ID: {script_id}, version: {version}")
    """
    if not indicators:
        print("No indicators found.")
        return None

    print("\n-- Enter the number of your preferred indicator:")
    for idx, item in enumerate(indicators, start=1):
        print(f"{idx}- {item.script_name} by {item.author}")

    try:
        selected_index: int = int(input("Your choice: ")) - 1
    except ValueError:
        print("Invalid input. Please enter a number.")
        return None

    if 0 <= selected_index < len(indicators):
        selected_indicator: IndicatorData = indicators[selected_index]
        print(
            f"You selected: {selected_indicator.script_name} by {selected_indicator.author}"
        )
        return (
            selected_indicator.script_id_part,
            selected_indicator.version,
        )
    else:
        print("Invalid selection.")
        return None


async def fetch_indicator_metadata(
    script_id: str, script_version: str, chart_session: str
) -> Dict[str, Any]:
    """
    Fetch metadata for a TradingView indicator based on its script ID and version asynchronously.

    This function constructs a URL using the provided script ID and version, sends a GET
    request to fetch the indicator metadata, and then prepares the metadata for further
    processing using the chart session.

    Args:
        script_id: The unique identifier for the indicator script.
        script_version: The version of the indicator script.
        chart_session: The chart session identifier used in further processing.

    Returns:
        A dictionary containing the prepared indicator metadata if successful;
        an empty dictionary is returned if an error occurs.

    Raises:
        httpx.HTTPError: If there's an HTTP-related error during the request.

    Example:
        >>> metadata = await fetch_indicator_metadata("PUB;123", "1.0", "session123")
        >>> if metadata:
        ...     print("Metadata fetched successfully")
    """
    url: str = f"https://pine-facade.tradingview.com/pine-facade/translate/{script_id}/{script_version}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response: httpx.Response = await client.get(url=url)
            response.raise_for_status()
            json_data: Dict[str, Any] = response.json()

            metainfo: Optional[Dict[str, Any]] = json_data.get("result", {}).get(
                "metaInfo"
            )
            if metainfo:
                return prepare_indicator_metadata(
                    script_id=script_id, metainfo=metainfo, chart_session=chart_session
                )

            return {}

    except httpx.RequestError as exc:
        logging.error("Error fetching indicator metadata: %s", exc)
        return {}


def prepare_indicator_metadata(
    script_id: str, metainfo: Dict[str, Any], chart_session: str
) -> Dict[str, Any]:
    """
    Prepare indicator metadata into the required payload structure.

    This function constructs a dictionary payload for creating a study (indicator) session.
    It extracts default input values and metadata from the provided metainfo and combines them
    with the provided script ID and chart session.

    Args:
        script_id: The unique identifier for the indicator script.
        metainfo: A dictionary containing metadata information for the indicator.
        chart_session: The chart session identifier.

    Returns:
        A dictionary representing the payload required to create a study with the indicator.

    Example:
        >>> metainfo = {"inputs": [{"defval": "test", "id": "in_param1", "type": "string"}]}
        >>> payload = prepare_indicator_metadata("PUB;123", metainfo, "session123")
        >>> print(payload["m"])  # "create_study"
    """
    # Create Pydantic models for structured data
    pine_features: PineFeatures = PineFeatures(
        v='{"indicator":1,"plot":1,"ta":1}', f=True, t="text"
    )

    profile_config: ProfileConfig = ProfileConfig(v=False, f=True, t="bool")

    # Base study configuration
    study_config: Dict[str, Any] = {
        "text": metainfo["inputs"][0]["defval"],
        "pineId": script_id,
        "pineVersion": metainfo.get("pine", {}).get("version", "1.0"),
        "pineFeatures": pine_features.model_dump(),
        "__profile": profile_config.model_dump(),
    }

    # Collect additional input values that start with 'in_'
    input_values: Dict[str, Dict[str, Any]] = {}
    for input_item in metainfo.get("inputs", []):
        if input_item["id"].startswith("in_"):
            input_value: InputValue = InputValue(
                v=input_item["defval"], f=True, t=input_item["type"]
            )
            input_values[input_item["id"]] = input_value.model_dump()

    # Update study config with additional inputs
    study_config.update(input_values)

    # Create the study payload
    study_payload: StudyPayload = StudyPayload(
        m="create_study",
        p=[
            chart_session,
            "st9",
            "st1",
            "sds_1",
            "Script@tv-scripting-101!",
            study_config,
        ],
    )

    return study_payload.model_dump()


if __name__ == "__main__":
    # Example usage of the module functions can be placed here for testing purposes.

    async def main() -> None:
        # Example: Validate a symbol
        print("Validating symbols...")
        market_symbol: str = "BINANCE:BTCUSDT"
        try:
            is_valid: bool = await validate_symbols(exchange_symbol=market_symbol)
            print(f"Symbol '{market_symbol}' is valid: {is_valid}")
        except ValueError as e:
            print(f"Validation error: {e}")

        # Example: Fetch TradingView indicators
        print("Fetching TradingView indicators...")
        indicator_name: str = "RSI"
        indicators: List[IndicatorData] = await fetch_tradingview_indicators(
            query=indicator_name
        )
        if indicators:
            selected: Optional[Tuple[Optional[str], Optional[str]]] = (
                display_and_select_indicator(indicators=indicators)
            )
            if selected:
                script_id: Optional[str]
                version: Optional[str]
                script_id, version = selected
                print(f"Selected script ID: {script_id}, version: {version}")
        else:
            print("No indicators found.")

    asyncio.run(main())
