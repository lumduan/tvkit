"""
TradingView indicator service for searching, selecting, and managing Pine script indicators.

This module provides async functions for interacting with TradingView's indicator API,
including searching for indicators, interactive selection, and metadata fetching.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .models import IndicatorData, InputValue, PineFeatures, ProfileConfig, StudyPayload


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
