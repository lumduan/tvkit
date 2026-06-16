"""
TradingView indicator service for searching, selecting, and managing Pine script indicators.

This module provides async functions for interacting with TradingView's indicator API,
including searching for indicators, interactive selection, and metadata fetching.
"""

import logging
from typing import Any

import httpx
from pydantic import ValidationError

from .models import IndicatorData, InputValue, PineFeatures, ProfileConfig, StudyPayload

logger: logging.Logger = logging.getLogger(__name__)


async def fetch_tradingview_indicators(query: str) -> list[IndicatorData]:
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
            json_data: Any = response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("TradingView indicator search returned an error status: %s", exc)
        return []
    except httpx.RequestError as exc:
        logger.error("Error fetching TradingView indicators: %s", exc)
        return []
    except ValueError as exc:  # json.JSONDecodeError is a ValueError subclass
        logger.error("Failed to decode TradingView indicator response: %s", exc)
        return []

    results: list[Any] = json_data.get("results", []) if isinstance(json_data, dict) else []
    query_lower: str = query.lower()
    filtered_results: list[IndicatorData] = []

    for indicator in results:
        # Defensive parsing: TradingView's public endpoint occasionally returns
        # entries missing expected keys. Skip malformed records instead of letting
        # a single KeyError/TypeError abort the entire search.
        if not isinstance(indicator, dict):
            continue

        script_name: Any = indicator.get("scriptName")
        author: Any = indicator.get("author")
        username: Any = author.get("username") if isinstance(author, dict) else None

        if not isinstance(script_name, str) or not isinstance(username, str):
            logger.debug("Skipping malformed indicator entry: %r", indicator)
            continue

        if query_lower not in script_name.lower() and query_lower not in username.lower():
            continue

        try:
            filtered_results.append(
                IndicatorData(
                    script_name=script_name,
                    image_url=indicator.get("imageUrl", ""),
                    author=username,
                    agree_count=indicator.get("agreeCount", 0),
                    is_recommended=indicator.get("isRecommended", False),
                    script_id_part=indicator.get("scriptIdPart", ""),
                    version=indicator.get("version"),
                )
            )
        except (ValidationError, TypeError) as exc:
            logger.debug("Skipping indicator that failed validation: %s", exc)
            continue

    return filtered_results


def display_and_select_indicator(
    indicators: list[IndicatorData],
) -> tuple[str | None, str | None] | None:
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
        print(f"You selected: {selected_indicator.script_name} by {selected_indicator.author}")
        return (
            selected_indicator.script_id_part,
            selected_indicator.version,
        )
    else:
        print("Invalid selection.")
        return None


async def fetch_indicator_metadata(
    script_id: str, script_version: str, chart_session: str
) -> dict[str, Any]:
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
    url: str = (
        f"https://pine-facade.tradingview.com/pine-facade/translate/{script_id}/{script_version}"
    )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response: httpx.Response = await client.get(url=url)
            response.raise_for_status()
            json_data: dict[str, Any] = response.json()

            result: Any = json_data.get("result", {}) if isinstance(json_data, dict) else {}
            metainfo: Any = result.get("metaInfo") if isinstance(result, dict) else None
            if isinstance(metainfo, dict) and metainfo:
                return prepare_indicator_metadata(
                    script_id=script_id, metainfo=metainfo, chart_session=chart_session
                )

            return {}

    except httpx.HTTPStatusError as exc:
        logger.error("Indicator metadata request returned an error status: %s", exc)
        return {}
    except httpx.RequestError as exc:
        logger.error("Error fetching indicator metadata: %s", exc)
        return {}
    except ValueError as exc:  # json.JSONDecodeError is a ValueError subclass
        logger.error("Failed to decode indicator metadata response: %s", exc)
        return {}


def prepare_indicator_metadata(
    script_id: str, metainfo: dict[str, Any], chart_session: str
) -> dict[str, Any]:
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

    # Base study configuration. Extract the first input's default value defensively:
    # malformed metadata (missing/empty "inputs", non-dict entries) must not raise
    # IndexError/KeyError and abort study creation.
    inputs: list[Any] = metainfo.get("inputs", [])
    first_input: dict[str, Any] = inputs[0] if inputs and isinstance(inputs[0], dict) else {}
    pine: Any = metainfo.get("pine")
    pine_version: str = pine.get("version", "1.0") if isinstance(pine, dict) else "1.0"
    study_config: dict[str, Any] = {
        "text": first_input.get("defval", ""),
        "pineId": script_id,
        "pineVersion": pine_version,
        "pineFeatures": pine_features.model_dump(),
        "__profile": profile_config.model_dump(),
    }

    # Collect additional input values that start with 'in_'
    input_values: dict[str, dict[str, Any]] = {}
    for input_item in inputs:
        if not isinstance(input_item, dict):
            continue
        input_id: Any = input_item.get("id")
        input_type: Any = input_item.get("type")
        if (
            not isinstance(input_id, str)
            or not input_id.startswith("in_")
            or "defval" not in input_item
            or not isinstance(input_type, str)
        ):
            continue
        input_value: InputValue = InputValue(v=input_item["defval"], f=True, t=input_type)
        input_values[input_id] = input_value.model_dump()

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
