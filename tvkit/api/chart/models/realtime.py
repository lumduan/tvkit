from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtraRequestHeader(BaseModel):
    """
    Pydantic model for HTTP request headers used in TradingView WebSocket handshake.

    All fields are validated and have explicit type annotations and descriptions.
    """

    accept_encoding: Optional[str] = Field(
        default="gzip, deflate, br, zstd",
        # alias="Accept-Encoding",
        description="Accepted content encodings for HTTP response.",
    )
    accept_language: Optional[str] = Field(
        default="en-US,en;q=0.9,fa;q=0.8",
        # alias="Accept-Language",
        description="Preferred languages for response.",
    )
    cache_control: Optional[str] = Field(
        default="no-cache",
        # alias="Cache-Control",
        description="Cache control directives.",
    )
    origin: Optional[str] = Field(
        default="https://www.tradingview.com",
        # alias="Origin",
        description="Originating site for the request.",
    )
    pragma: Optional[str] = Field(
        default="no-cache",
        # alias="Pragma",
        description="Pragma header for backward compatibility with HTTP/1.0 caches.",
    )
    user_agent: Optional[str] = Field(
        default="Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
        # alias="User-Agent",
        description="User agent string identifying the client.",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @field_validator("origin")
    @classmethod
    def validate_origin(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("Origin must start with 'https://'")
        return v

    @field_validator("user_agent")
    @classmethod
    def validate_user_agent(cls, v: str) -> str:
        if "Mozilla" not in v:
            raise ValueError("User-Agent must contain 'Mozilla'")
        return v


class WebSocketConnection(BaseModel):
    uri: str = Field(
        "wss://data.tradingview.com/socket.io/websocket?from=screener%2F",
        description="WebSocket URI to connect to",
    )
    additional_headers: ExtraRequestHeader = Field(
        default=ExtraRequestHeader(),
        description="HTTP headers to include in the WebSocket handshake",
    )
    compression: str = Field(
        "deflate", description="WebSocket compression method by default is 'deflate'"
    )
    ping_interval: int = Field(20, description="Ping interval in seconds")
    ping_timeout: int = Field(10, description="Ping timeout in seconds")
    close_timeout: int = Field(10, description="Close timeout in seconds")
