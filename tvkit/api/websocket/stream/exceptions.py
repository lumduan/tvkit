"""
Exception classes for TradingView WebSocket streaming.

This module defines custom exceptions used throughout the streaming functionality.
"""

from typing import Optional, Any


class StreamingError(Exception):
    """Base exception for streaming-related errors."""

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        """
        Initialize the StreamingError.

        Args:
            message: The main error message
            details: Optional additional details about the error
        """
        self.message: str = message
        self.details: Optional[Any] = details
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class DataNotFoundError(StreamingError):
    """Raised when expected data is not found in the stream."""

    def __init__(self, message: str = "Expected data not found in stream", details: Optional[Any] = None) -> None:
        """
        Initialize the DataNotFoundError.

        Args:
            message: The error message
            details: Optional additional details about the error
        """
        super().__init__(message, details)


class ConnectionError(StreamingError):
    """Raised when WebSocket connection issues occur."""

    def __init__(self, message: str = "WebSocket connection error", details: Optional[Any] = None) -> None:
        """
        Initialize the ConnectionError.

        Args:
            message: The error message
            details: Optional additional details about the error
        """
        super().__init__(message, details)


class ValidationError(StreamingError):
    """Raised when symbol or parameter validation fails."""

    def __init__(self, message: str = "Validation error", details: Optional[Any] = None) -> None:
        """
        Initialize the ValidationError.

        Args:
            message: The error message
            details: Optional additional details about the error
        """
        super().__init__(message, details)


class SymbolValidationError(ValidationError):
    """
    Exception raised when symbol validation fails.

    This exception is raised when a trading symbol is invalid, malformed,
    or not supported by the exchange.
    """

    def __init__(self, symbol: str, message: Optional[str] = None, details: Optional[Any] = None):
        """
        Initialize the symbol validation error.

        Args:
            symbol: The invalid symbol that caused the error.
            message: Optional custom error message.
            details: Additional validation error details.
        """
        self.symbol: str = symbol
        error_msg: str = message or f"Invalid symbol: {symbol}"
        super().__init__(error_msg, details)


class DataParsingError(StreamingError):
    """
    Exception raised when received data cannot be parsed correctly.

    This exception is raised when WebSocket message data is malformed,
    contains unexpected values, or cannot be converted to expected types.
    """

    def __init__(self, message: str = "Data parsing error", raw_data: Optional[Any] = None):
        """
        Initialize the data parsing error.

        Args:
            message: Error message describing the parsing issue.
            raw_data: The raw data that failed to parse.
        """
        super().__init__(message, raw_data)
        self.raw_data: Optional[Any] = raw_data


class SessionError(StreamingError):
    """
    Exception raised when session management fails.

    This exception is raised for issues with WebSocket session creation,
    authentication, or session-related operations.
    """

    def __init__(self, message: str = "Session management error", session_id: Optional[str] = None):
        """
        Initialize the session error.

        Args:
            message: Error message describing the session issue.
            session_id: The session identifier if available.
        """
        super().__init__(message, session_id)
        self.session_id: Optional[str] = session_id


class ExportError(StreamingError):
    """
    Exception raised when data export operations fail.

    This exception is raised when file writing, format conversion,
    or other export-related operations encounter errors.
    """

    def __init__(self, message: str = "Data export error", filepath: Optional[str] = None):
        """
        Initialize the export error.

        Args:
            message: Error message describing the export issue.
            filepath: The file path that failed during export.
        """
        super().__init__(message, filepath)
        self.filepath: Optional[str] = filepath


class RateLimitError(StreamingError):
    """
    Exception raised when API rate limits are exceeded.

    This exception is raised when too many requests are made within
    a specified time period, triggering rate limiting.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        limit_type: Optional[str] = None
    ):
        """
        Initialize the rate limit error.

        Args:
            message: Error message describing the rate limit issue.
            retry_after: Seconds to wait before retrying, if known.
            limit_type: Type of rate limit (e.g., 'connections', 'requests').
        """
        super().__init__(message, {'retry_after': retry_after, 'limit_type': limit_type})
        self.retry_after: Optional[int] = retry_after
        self.limit_type: Optional[str] = limit_type


class ConfigurationError(StreamingError):
    """
    Exception raised when configuration is invalid or incomplete.

    This exception is raised when stream configuration contains
    invalid parameters, missing required fields, or conflicting settings.
    """

    def __init__(self, message: str = "Configuration error", config_field: Optional[str] = None):
        """
        Initialize the configuration error.

        Args:
            message: Error message describing the configuration issue.
            config_field: The specific configuration field causing the error.
        """
        super().__init__(message, config_field)
        self.config_field: Optional[str] = config_field


class TimeoutError(StreamingError):
    """
    Exception raised when operations exceed specified timeout limits.

    This exception is raised when WebSocket operations, HTTP requests,
    or other async operations take longer than expected.
    """

    def __init__(
        self,
        message: str = "Operation timed out",
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None
    ):
        """
        Initialize the timeout error.

        Args:
            message: Error message describing the timeout.
            timeout_seconds: The timeout value that was exceeded.
            operation: The operation that timed out.
        """
        super().__init__(message, {'timeout_seconds': timeout_seconds, 'operation': operation})
        self.timeout_seconds: Optional[float] = timeout_seconds
        self.operation: Optional[str] = operation


class AuthenticationError(StreamingError):
    """
    Exception raised when authentication fails.

    This exception is raised when JWT tokens are invalid, expired,
    or authentication with the WebSocket service fails.
    """

    def __init__(self, message: str = "Authentication failed", token_type: Optional[str] = None):
        """
        Initialize the authentication error.

        Args:
            message: Error message describing the authentication issue.
            token_type: The type of token that failed authentication.
        """
        super().__init__(message, token_type)
        self.token_type: Optional[str] = token_type
