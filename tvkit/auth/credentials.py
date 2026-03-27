"""TradingView credential models for tvkit.auth."""

from dataclasses import dataclass, field

__all__ = ["TradingViewCredentials"]


@dataclass
class TradingViewCredentials:
    """
    Authentication credentials for a TradingView session.

    Provide exactly one of the following credential sources:

    - **``browser``**: ``"chrome"`` or ``"firefox"`` — tvkit extracts session
      cookies from the named browser. The user must already be logged in to
      TradingView in that browser. Supports transparent re-authentication by
      re-reading cookies on WebSocket auth error.
    - **``cookies``**: Pre-extracted cookie dict (name→value). Advanced fallback
      for environments without a browser (CI/CD, headless servers). Caller is
      responsible for providing valid, non-expired cookies.
    - **``auth_token``**: Pre-obtained TradingView auth token. Bypasses cookie
      extraction entirely. Caller is responsible for token refresh; tvkit cannot
      re-authenticate without a valid browser session.
    - **Anonymous** (default): all fields ``None`` — uses
      ``"unauthorized_user_token"`` for backward-compatible anonymous access.

    ``browser_profile`` is an optional companion to ``browser``, used to target
    a specific Chrome or Firefox profile on multi-profile machines.

    Args:
        browser: Browser to extract cookies from. Must be ``"chrome"`` or
            ``"firefox"``. Mutually exclusive with ``cookies`` and ``auth_token``.
        browser_profile: Specific browser profile name (e.g. ``"Default"``,
            ``"Profile 2"``). Only valid when ``browser`` is set. If omitted,
            the browser's default profile is used.
        cookies: Pre-extracted cookie dict bypassing browser extraction.
            Mutually exclusive with ``browser`` and ``auth_token``.
        auth_token: Pre-obtained auth token bypassing cookie extraction entirely.
            Mutually exclusive with ``browser`` and ``cookies``.

    Raises:
        ValueError: If more than one credential source is provided, if
            ``browser`` is not ``"chrome"`` or ``"firefox"``, or if
            ``browser_profile`` is set without ``browser``.

    Example:
        >>> creds = TradingViewCredentials(browser="chrome")
        >>> creds.uses_browser
        True
        >>> creds.is_anonymous
        False

        >>> creds = TradingViewCredentials()
        >>> creds.is_anonymous
        True
    """

    browser: str | None = None
    browser_profile: str | None = None
    cookies: dict[str, str] | None = field(default=None, repr=False)
    auth_token: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        sources = sum(
            [
                self.browser is not None,
                self.cookies is not None,
                self.auth_token is not None,
            ]
        )
        if sources > 1:
            raise ValueError(
                "Provide exactly one of: browser, cookies, or auth_token — not multiple."
            )
        if self.browser is not None and self.browser not in {"chrome", "firefox"}:
            raise ValueError(
                f"Unsupported browser: {self.browser!r}. Choose 'chrome' or 'firefox'."
            )
        if self.browser_profile is not None and self.browser is None:
            raise ValueError(
                "browser_profile requires browser to be set. "
                "Provide browser='chrome' or browser='firefox'."
            )

    @property
    def is_anonymous(self) -> bool:
        """Return ``True`` if no credential source is provided."""
        return self.browser is None and self.cookies is None and self.auth_token is None

    @property
    def uses_browser(self) -> bool:
        """Return ``True`` if browser cookie extraction is configured."""
        return self.browser is not None

    @property
    def uses_cookie_dict(self) -> bool:
        """Return ``True`` if a pre-extracted cookie dict was provided."""
        return self.cookies is not None

    @property
    def uses_direct_token(self) -> bool:
        """Return ``True`` if a pre-obtained ``auth_token`` was provided."""
        return self.auth_token is not None
