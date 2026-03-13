"""Exception types for the tvkit.auth package."""

__all__ = [
    "AuthError",
    "AuthenticationError",
    "CapabilityProbeError",
    "ProfileFetchError",
]


class AuthError(Exception):
    """
    Base exception for all tvkit.auth errors.

    Allows callers to catch any authentication-related failure
    with a single ``except AuthError`` clause.
    """


class AuthenticationError(AuthError):
    """
    Raised when TradingView authentication fails.

    Covers:

    - Wrong credentials (HTTP 401)
    - Session expiry requiring full re-login (HTTP 403)
    - CSRF bootstrap failure (``csrftoken`` cookie absent)
    - Login timeout after one retry
    - Re-login loop detection (HTTP 401 persists after re-login attempt)
    """


class ProfileFetchError(AuthError):
    """
    Raised when the TradingView user profile cannot be extracted
    from the homepage bootstrap payload.

    Covers:

    - All 3 bootstrap extraction strategies failing
    - ``"user": null`` (logged-out state — credentials rejected)
    - ``"user": {}`` (partial payload — payload corruption)
    - Missing ``id`` or ``username`` fields
    - Missing ``auth_token`` field
    """


class CapabilityProbeError(AuthError):
    """
    Raised when the background capability probe fails.

    This error is **non-fatal**. ``AuthManager`` catches it, logs a WARNING,
    and retains the plan-based ``estimated_max_bars`` value as the fallback.
    The primary connection and authentication remain unaffected.
    """
