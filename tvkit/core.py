"""
TVKit Core Module

Core functionality for the TVKit library.
"""

def get_version() -> str:
    """Get the current version of TVKit."""
    from . import __version__
    return __version__

def hello_tvkit() -> str:
    """Simple hello function to verify the package is working."""
    return "Hello from TVKit - TradingView API Integration Library!"
