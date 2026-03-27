"""
tvkit.auth — TradingView account authentication and capability detection.

Public API
----------
- ``AuthManager`` — async context manager for the full auth flow.
- ``TradingViewCredentials`` — credentials dataclass (anonymous / browser / cookie dict / direct token).
- ``TradingViewAccount`` — authenticated account profile and capability limits.
- ``CookieProvider`` — browser cookie extraction via ``browser_cookie3``.
- ``AuthError`` — base exception for all auth errors.
- ``BrowserCookieError`` — browser extraction failures (not installed, sessionid absent).
- ``ProfileFetchError`` — homepage bootstrap parse failures or missing auth_token.
- ``CapabilityProbeError`` — background probe failure (non-fatal).

Basic usage::

    from tvkit.auth import AuthManager, TradingViewCredentials

    # Anonymous (default — zero changes required for existing code)
    async with AuthManager() as auth:
        token = auth.auth_token  # "unauthorized_user_token"

    # Browser cookie extraction (Chrome)
    creds = TradingViewCredentials(browser="chrome")
    async with AuthManager(creds) as auth:
        token = auth.auth_token     # real TradingView auth token
        account = auth.account      # TradingViewAccount(tier="premium", ...)

    # Direct token injection (CI/CD — caller manages refresh)
    creds = TradingViewCredentials(auth_token="tv_auth_token_here")
    async with AuthManager(creds) as auth:
        token = auth.auth_token
"""

from tvkit.auth.auth_manager import AuthManager
from tvkit.auth.cookie_provider import CookieProvider
from tvkit.auth.credentials import TradingViewCredentials
from tvkit.auth.exceptions import (
    AuthError,
    BrowserCookieError,
    CapabilityProbeError,
    ProfileFetchError,
)
from tvkit.auth.models import TradingViewAccount

__all__ = [
    "AuthError",
    "AuthManager",
    "BrowserCookieError",
    "CapabilityProbeError",
    "CookieProvider",
    "ProfileFetchError",
    "TradingViewAccount",
    "TradingViewCredentials",
]
