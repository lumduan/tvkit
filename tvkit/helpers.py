"""
Helper functions to improve user experience and provide better error messages.
"""

import sys
from typing import List, Optional


class TVKitError(Exception):
    """Base exception for TVKit with helpful error messages."""

    def __init__(self, message: str, suggestions: Optional[List[str]] = None):
        self.suggestions = suggestions or []
        super().__init__(message)

    def __str__(self) -> str:
        msg = super().__str__()
        if self.suggestions:
            suggestions_text = "\n".join(f"  • {s}" for s in self.suggestions)
            msg += f"\n\n💡 Suggestions:\n{suggestions_text}"
        return msg


class SymbolValidationError(TVKitError):
    """Error for invalid trading symbols with helpful suggestions."""

    def __init__(self, symbol: str, message: str = ""):
        suggestions = [
            f"Check symbol format: '{symbol}' should be like 'EXCHANGE:SYMBOL'",
            "Popular examples: 'NASDAQ:AAPL', 'BINANCE:BTCUSDT', 'FX_IDC:EURUSD'",
            "Use tvkit.POPULAR_STOCKS or tvkit.MAJOR_CRYPTOS for valid symbols",
            "Search TradingView.com to find the correct symbol format",
        ]

        if not message:
            message = f"Invalid symbol: '{symbol}'"

        super().__init__(message, suggestions)


class ConnectionError(TVKitError):
    """Error for connection issues with troubleshooting tips."""

    def __init__(self, message: str = "Failed to connect to TradingView"):
        suggestions = [
            "Check your internet connection",
            "Verify that TradingView.com is accessible",
            "Try again in a few moments (may be rate limited)",
            "Check firewall settings if using corporate network",
            "Consider using a VPN if region-blocked",
        ]
        super().__init__(message, suggestions)


class PythonVersionError(TVKitError):
    """Error for unsupported Python versions."""

    def __init__(self):
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        message = f"TVKit requires Python 3.11 or higher. You're using Python {current_version}"
        suggestions = [
            "Upgrade Python: https://www.python.org/downloads/",
            "Use pyenv to manage multiple Python versions",
            "Consider using uv for automatic Python management: 'uv python install 3.11'",
            "Check if your system has a newer Python version available",
        ]
        super().__init__(message, suggestions)


def check_python_version():
    """Check if Python version is supported."""
    if sys.version_info < (3, 11):
        raise PythonVersionError()


def validate_symbol_format(symbol: str) -> bool:
    """
    Validate that a symbol follows the expected format.

    Args:
        symbol: Trading symbol to validate

    Returns:
        True if valid format

    Raises:
        SymbolValidationError: If symbol format is invalid
    """
    if not symbol or not isinstance(symbol, str):
        raise SymbolValidationError(symbol, "Symbol must be a non-empty string")

    if ":" not in symbol:
        raise SymbolValidationError(
            symbol, f"Symbol '{symbol}' missing exchange prefix"
        )

    parts = symbol.split(":")
    if len(parts) != 2:
        raise SymbolValidationError(
            symbol, f"Symbol '{symbol}' should have exactly one ':' separator"
        )

    exchange, ticker = parts
    if not exchange or not ticker:
        raise SymbolValidationError(
            symbol, f"Both exchange and ticker must be specified in '{symbol}'"
        )

    return True


def provide_symbol_suggestions(failed_symbol: str) -> List[str]:
    """
    Provide helpful symbol suggestions when a symbol fails.

    Args:
        failed_symbol: The symbol that failed

    Returns:
        List of suggestion strings
    """
    suggestions = []

    # Check if it looks like a US stock without exchange
    if failed_symbol.isupper() and len(failed_symbol) <= 5 and ":" not in failed_symbol:
        suggestions.extend(
            [
                f"Try 'NASDAQ:{failed_symbol}' for NASDAQ stocks",
                f"Try 'NYSE:{failed_symbol}' for NYSE stocks",
            ]
        )

    # Check if it looks like crypto
    if any(crypto in failed_symbol.upper() for crypto in ["BTC", "ETH", "ADA", "SOL"]):
        crypto_base = failed_symbol.upper().replace("USD", "").replace("USDT", "")
        suggestions.append(f"Try 'BINANCE:{crypto_base}USDT' for cryptocurrency")

    # Check if it looks like forex
    if len(failed_symbol) == 6 and failed_symbol.isalpha():
        suggestions.append(f"Try 'FX_IDC:{failed_symbol}' for forex pairs")

    # General suggestions
    suggestions.extend(
        [
            "Use tvkit.POPULAR_STOCKS for common stock symbols",
            "Use tvkit.MAJOR_CRYPTOS for major cryptocurrency symbols",
            "Search on TradingView.com to find the correct symbol",
        ]
    )

    return suggestions


def create_user_friendly_error(error: Exception, context: str = "") -> str:
    """
    Convert technical errors into user-friendly messages.

    Args:
        error: The original exception
        context: Additional context about what was being attempted

    Returns:
        User-friendly error message
    """
    error_type = type(error).__name__
    error_msg = str(error)

    # Common error patterns and their user-friendly versions
    if "timeout" in error_msg.lower():
        return f"⏱️ Request timed out{' while ' + context if context else ''}. Try again in a moment."

    if "connection" in error_msg.lower() or "network" in error_msg.lower():
        return f"🌐 Network connection issue{' while ' + context if context else ''}. Check your internet connection."

    if "unauthorized" in error_msg.lower() or "403" in error_msg:
        return f"🔒 Access denied{' while ' + context if context else ''}. This might be due to rate limiting."

    if "not found" in error_msg.lower() or "404" in error_msg:
        return f"❓ Resource not found{' while ' + context if context else ''}. Check the symbol or parameters."

    if "invalid" in error_msg.lower() and "symbol" in error_msg.lower():
        return f"🎯 Invalid symbol format{' while ' + context if context else ''}. Use format like 'NASDAQ:AAPL'."

    # Default fallback
    return f"❌ {error_type}: {error_msg}{' (context: ' + context + ')' if context else ''}"


def get_help_message() -> str:
    """Get a helpful message for users who need assistance."""
    return """
🆘 Need Help with TVKit?

📚 Quick Resources:
  • README: https://github.com/lumduan/tvkit#readme
  • Examples: Run 'uv run python examples/quick_tutorial.py'
  • PyPI Page: https://pypi.org/project/tvkit/

🚀 Quick Start:
  >>> import tvkit
  >>> price = tvkit.run_async(tvkit.get_stock_price("NASDAQ:AAPL"))
  >>> print(f"Apple: ${price['price']}")

🎯 Common Symbol Formats:
  • US Stocks: NASDAQ:AAPL, NYSE:JPM
  • Crypto: BINANCE:BTCUSDT, BINANCE:ETHUSDT
  • Forex: FX_IDC:EURUSD, FX_IDC:GBPUSD

💡 Pre-defined Lists:
  • tvkit.POPULAR_STOCKS - Top US stocks
  • tvkit.MAJOR_CRYPTOS - Major cryptocurrencies
  • tvkit.FOREX_PAIRS - Common forex pairs

🐛 Issues? Report at: https://github.com/lumduan/tvkit/issues
"""


# Version check on import
try:
    check_python_version()
except PythonVersionError:
    # Don't raise immediately on import, just warn
    import warnings

    warnings.warn(
        f"TVKit works best with Python 3.11+. You're using {sys.version_info.major}.{sys.version_info.minor}. "
        "Some features may not work as expected.",
        UserWarning,
        stacklevel=2,
    )
