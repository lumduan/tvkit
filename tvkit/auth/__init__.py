"""
tvkit.auth — TradingView account authentication and capability detection.

Public API
----------
- ``AuthManager`` — async context manager for the full auth flow.
- ``TradingViewCredentials`` — credentials dataclass (anonymous / login / direct token).
- ``TradingViewAccount`` — authenticated account profile and capability limits.
- ``AuthError`` — base exception for all auth errors.
- ``AuthenticationError`` — login failures, wrong credentials, re-login loop.
- ``ProfileFetchError`` — homepage bootstrap parse failures.
- ``CapabilityProbeError`` — background probe failure (non-fatal).

Basic usage::

    from tvkit.auth import AuthManager, TradingViewCredentials

    # Anonymous (default)
    async with AuthManager() as auth:
        token = auth.auth_token  # "unauthorized_user_token"

    # Authenticated
    creds = TradingViewCredentials(username="alice", password="s3cr3t")
    async with AuthManager(creds) as auth:
        token = auth.auth_token     # real TradingView auth token
        account = auth.account      # TradingViewAccount(tier="premium", ...)
"""

from tvkit.auth.auth_manager import AuthManager
from tvkit.auth.credentials import TradingViewCredentials
from tvkit.auth.exceptions import (
    AuthenticationError,
    AuthError,
    CapabilityProbeError,
    ProfileFetchError,
)
from tvkit.auth.models import TradingViewAccount

__all__ = [
    "AuthError",
    "AuthManager",
    "AuthenticationError",
    "CapabilityProbeError",
    "ProfileFetchError",
    "TradingViewAccount",
    "TradingViewCredentials",
]
