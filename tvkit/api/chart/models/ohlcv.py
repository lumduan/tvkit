"""
OHLCV models for TradingView WebSocket streaming data.

This module provides type-safe Pydantic models for parsing and validating
OHLCV (Open, High, Low, Close, Volume) data received from TradingView's
WebSocket API.
"""

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class OHLCVBar(BaseModel):
    """
    Represents a single OHLCV (Open, High, Low, Close, Volume) candlestick bar.

    This model contains all price and volume data for a specific time period.
    """

    model_config = ConfigDict(extra="forbid")

    timestamp: float = Field(description="Unix timestamp for the bar start time")
    open: float = Field(description="Opening price for the time period")
    high: float = Field(description="Highest price during the time period")
    low: float = Field(description="Lowest price during the time period")
    close: float = Field(description="Closing price for the time period")
    volume: float = Field(description="Total volume traded during the time period")

    @classmethod
    def from_array(cls, data: List[float]) -> "OHLCVBar":
        """
        Create an OHLCVBar from TradingView's array format.

        Args:
            data: Array in format [timestamp, open, high, low, close, volume]
                  or [timestamp, open, high, low, close] (volume defaults to 0)

        Returns:
            OHLCVBar instance

        Raises:
            ValueError: If data array doesn't have 5 or 6 elements
        """
        if len(data) < 5 or len(data) > 6:
            raise ValueError(
                f"Expected 5 or 6 elements in OHLCV array, got {len(data)}"
            )

        return cls(
            timestamp=data[0],
            open=data[1],
            high=data[2],
            low=data[3],
            close=data[4],
            volume=data[5]
            if len(data) == 6
            else 0.0,  # Default volume to 0 if not provided
        )


class SeriesData(BaseModel):
    """
    Represents series data containing OHLCV bars and metadata.
    """

    model_config = ConfigDict(extra="forbid")

    index: int = Field(alias="i", description="Bar index in the series")
    values: List[float] = Field(
        alias="v",
        description="OHLCV values array [timestamp, open, high, low, close, volume]",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ohlcv_bar(self) -> OHLCVBar:
        """
        Convert the values array to a structured OHLCVBar object.

        Returns:
            OHLCVBar: Structured OHLCV data
        """
        return OHLCVBar.from_array(self.values)


class NamespaceData(BaseModel):
    """
    Represents namespace data containing metadata about the data stream.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = Field(alias="d", default="", description="Data description")
    indexes: str = Field(default="nochange", description="Index change status")


class LastBarStatus(BaseModel):
    """
    Represents the last bar status information.
    """

    model_config = ConfigDict(extra="forbid")

    bar_close_time: float = Field(description="Unix timestamp when the bar closes")


class SeriesUpdate(BaseModel):
    """
    Represents a complete series update containing OHLCV data and metadata.
    """

    model_config = ConfigDict(extra="forbid")

    series_data: List[SeriesData] = Field(
        alias="s", description="List of series data points"
    )
    namespace: NamespaceData = Field(alias="ns", description="Namespace metadata")
    type: str = Field(alias="t", description="Series type identifier")
    last_bar_status: LastBarStatus = Field(
        alias="lbs", description="Last bar status information"
    )


class OHLCVResponse(BaseModel):
    """
    Complete OHLCV response model for TradingView WebSocket data updates.

    This model parses the complete response structure from TradingView's WebSocket API.
    Accepts both 'du' (data update) and 'timescale_update' message types.
    """

    model_config = ConfigDict(extra="allow")

    message_type: str = Field(
        alias="m", description="Message type ('du' or 'timescale_update')"
    )
    parameters: List[Any] = Field(
        alias="p", description="Message parameters containing session ID and data"
    )

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, v: str) -> str:
        """Validate that message type is a data update or timescale update."""
        if v not in ["du", "timescale_update"]:
            raise ValueError(
                f"Expected message type 'du' or 'timescale_update', got '{v}'"
            )
        return v

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v: List[Any]) -> List[Any]:
        """Validate parameters structure."""
        if len(v) < 2:
            raise ValueError("Parameters must contain at least session ID and data")
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def session_id(self) -> str:
        """
        Extract the session ID from parameters.

        Returns:
            str: WebSocket session identifier
        """
        return str(self.parameters[0])

    @computed_field  # type: ignore[prop-decorator]
    @property
    def series_updates(self) -> dict[str, SeriesUpdate]:
        """
        Extract and parse series updates from the response.

        Returns:
            dict[str, SeriesUpdate]: Dictionary mapping series names to their updates
        """
        if len(self.parameters) < 2:
            return {}

        data: dict[str, Any] = self.parameters[1]
        series_updates: dict[str, SeriesUpdate] = {}

        for series_name, series_data in data.items():
            try:
                series_updates[series_name] = SeriesUpdate.model_validate(series_data)
            except Exception:
                # Log but don't fail - allows partial parsing
                continue

        return series_updates

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ohlcv_bars(self) -> List[OHLCVBar]:
        """
        Extract all OHLCV bars from all series in the response.

        Returns:
            List[OHLCVBar]: List of all OHLCV bars in the update
        """
        bars: List[OHLCVBar] = []

        for series_update in self.series_updates.values():
            for series_data in series_update.series_data:
                bars.append(series_data.ohlcv_bar)

        return bars


class TimescaleUpdateResponse(BaseModel):
    """
    Model for timescale update messages containing historical OHLCV data.

    This handles the 'timescale_update' message format which has a different structure
    from regular 'du' messages.
    """

    model_config = ConfigDict(extra="allow")

    message_type: str = Field(
        alias="m", description="Message type ('timescale_update')"
    )
    parameters: List[Any] = Field(
        alias="p",
        description="Message parameters containing session ID and timescale data",
    )

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, v: str) -> str:
        """Validate that message type is timescale_update."""
        if v != "timescale_update":
            raise ValueError(f"Expected message type 'timescale_update', got '{v}'")
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def session_id(self) -> str:
        """Extract the session ID from parameters."""
        return str(self.parameters[0])

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ohlcv_bars(self) -> List[OHLCVBar]:
        """
        Extract all OHLCV bars from the timescale update.

        Returns:
            List[OHLCVBar]: List of all OHLCV bars in the update
        """
        bars: List[OHLCVBar] = []

        if len(self.parameters) < 2:
            return bars

        # The second parameter contains the series data
        series_data_dict: dict[str, Any] = self.parameters[1]

        # Look for series data (usually named like "sds_1")
        for series_info in series_data_dict.values():
            if isinstance(series_info, dict) and "s" in series_info:
                # Extract the series array
                series_array: List[Any] = series_info["s"]

                # Each item in the series has "i" (index) and "v" (values array)
                for item in series_array:
                    if isinstance(item, dict) and "v" in item:
                        values = item["v"]
                        if (
                            isinstance(values, list) and len(values) >= 5  # type: ignore[arg-type]
                        ):  # [timestamp, open, high, low, close] or [timestamp, open, high, low, close, volume]
                            try:
                                bars.append(OHLCVBar.from_array(values))  # type: ignore[arg-type]
                            except Exception:
                                continue  # Skip malformed bars

        return bars


class QuoteSymbolData(BaseModel):
    """
    Model for quote symbol data (message type 'qsd').

    This contains current price and symbol information for a specific instrument.
    """

    model_config = ConfigDict(extra="forbid")

    message_type: str = Field(
        alias="m", description="Message type ('qsd' for quote symbol data)"
    )
    parameters: List[Any] = Field(
        alias="p", description="Parameters containing session ID and quote data"
    )

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, v: str) -> str:
        """Validate that message type is quote symbol data."""
        if v != "qsd":
            raise ValueError(f"Expected message type 'qsd', got '{v}'")
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def session_id(self) -> str:
        """Extract the session ID from parameters."""
        return str(self.parameters[0]) if self.parameters else ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def quote_data(self) -> dict[str, Any]:
        """Extract quote data from parameters."""
        if len(self.parameters) >= 2 and isinstance(self.parameters[1], dict):
            return self.parameters[1]
        return {}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def current_price(self) -> Optional[float]:
        """Extract current price from quote data."""
        quote_data = self.quote_data
        if "v" in quote_data and isinstance(quote_data["v"], dict):
            return quote_data["v"].get("lp")  # 'lp' = last price
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def symbol_info(self) -> dict[str, Any]:
        """Extract symbol information from quote data."""
        quote_data = self.quote_data
        if "v" in quote_data and isinstance(quote_data["v"], dict):
            return quote_data["v"]
        return {}


class QuoteCompletedMessage(BaseModel):
    """
    Model for quote completion messages (message type 'quote_completed').

    These messages indicate that quote setup has been completed for a symbol.
    """

    model_config = ConfigDict(extra="forbid")

    message_type: str = Field(alias="m", description="Message type ('quote_completed')")
    parameters: List[Any] = Field(
        alias="p", description="Parameters containing session ID and symbol"
    )

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, v: str) -> str:
        """Validate that message type is quote completed."""
        if v != "quote_completed":
            raise ValueError(f"Expected message type 'quote_completed', got '{v}'")
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def session_id(self) -> str:
        """Extract the session ID from parameters."""
        return str(self.parameters[0]) if self.parameters else ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def symbol(self) -> str:
        """Extract the symbol from parameters."""
        return str(self.parameters[1]) if len(self.parameters) >= 2 else ""


class WebSocketMessage(BaseModel):
    """
    Generic WebSocket message model that can parse any TradingView message type.

    This is useful for debugging and handling unknown message types.
    """

    model_config = ConfigDict(extra="allow")

    message_type: str = Field(alias="m", description="Message type")
    parameters: List[Any] = Field(alias="p", description="Message parameters")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def session_id(self) -> str:
        """Extract the session ID from parameters if available."""
        return str(self.parameters[0]) if self.parameters else ""
