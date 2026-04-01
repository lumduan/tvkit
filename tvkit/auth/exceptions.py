"""Exception types for the tvkit.auth package."""

__all__ = [
    "AuthError",
    "BrowserCookieError",
    "CapabilityProbeError",
    "ProfileFetchError",
]


class AuthError(Exception):
    """
    Base exception for all tvkit.auth errors.

    Allows callers to catch any authentication-related failure
    with a single ``except AuthError`` clause.
    """


class BrowserCookieError(AuthError):
    """
    Raised when TradingView session cookies cannot be extracted from the browser.

    Covers:

    - ``browser_cookie3`` library not installed
    - ``browser_cookie3`` raises unexpectedly (e.g. locked database, permission denied)
    - ``sessionid`` cookie is absent — user is not logged in to TradingView in
      the selected browser, or the session has expired
    - Unsupported browser name passed to extraction

    This error is **not retried** automatically — the user must log in to
    TradingView in the browser and try again.
    """


class ProfileFetchError(AuthError):
    """
    Raised when the TradingView user profile cannot be extracted
    from the homepage bootstrap payload.

    Covers:

    - All 4 bootstrap extraction strategies failing
    - ``"user": null`` (logged-out state — session cookies are expired or invalid)
    - ``"user": {}`` (partial payload — payload corruption)
    - Missing ``id`` or ``username`` fields
    - ``auth_token`` missing, empty, or too short (< 10 characters)
    - HTTP 5xx or timeout after one retry
    """


class CapabilityProbeError(AuthError):
    """
    Raised when the background capability probe fails.

    This error is **non-fatal**. ``AuthManager`` catches it, logs a WARNING,
    and retains the plan-based ``estimated_max_bars`` value as the fallback.
    The primary connection and authentication remain unaffected.
    """
