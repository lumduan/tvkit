"""
Data models for TradingView utilities.

This module contains Pydantic data models used across the tvkit.api.utils package for
TradingView indicator management, Pine script configuration, and study payload structures.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class SymbolConversionResult(BaseModel):
    """Pydantic model for symbol format conversion result."""

    original_symbol: str = Field(
        ..., description="Original symbol in EXCHANGE-SYMBOL format"
    )
    converted_symbol: str = Field(
        ..., description="Converted symbol in EXCHANGE:SYMBOL format"
    )
    is_converted: bool = Field(..., description="Whether conversion was performed")

    model_config = {"frozen": True}
