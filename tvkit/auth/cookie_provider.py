"""TradingView browser cookie extraction for tvkit.auth."""

import logging
import time
from typing import Any

from tvkit.auth.exceptions import BrowserCookieError

__all__ = ["CookieProvider"]

logger: logging.Logger = logging.getLogger(__name__)

# In-memory cache TTL in seconds.  browser_cookie3 reads from disk and may
# access the macOS Keychain — extraction takes 100–300 ms on some machines.
COOKIE_CACHE_TTL: int = 120

_TV_DOMAIN: str = "tradingview.com"


def _get_browser_cookie3() -> Any:
    """Import browser_cookie3 lazily, raising a clear error if absent."""
    try:
        import browser_cookie3  # type: ignore[import-untyped]

        return browser_cookie3
    except ImportError:
        raise BrowserCookieError(
            "browser_cookie3 is required for browser cookie extraction. "
            "Install it with: uv add browser-cookie3"
        ) from None


class CookieProvider:
    """
    Extracts TradingView session cookies from a local browser's cookie store.

    Supports Chrome and Firefox via ``browser_cookie3``. Results are cached
    in memory with a TTL of ``COOKIE_CACHE_TTL`` seconds to avoid repeated
    disk I/O and macOS Keychain access.

    **Important:** When a WebSocket authentication error is detected, the cache
    for the affected browser/profile MUST be invalidated before re-extraction
    by calling :meth:`invalidate_cache`. This prevents tvkit from silently
    reusing stale cookies for up to the TTL window and entering an auth-fail loop.

    Example::

        provider = CookieProvider()
        cookies = provider.extract("chrome")
        # ... later, on WS auth error:
        provider.invalidate_cache("chrome")
        cookies = provider.extract("chrome")   # forces fresh disk read
    """

    def __init__(self) -> None:
        # Cache: (browser, profile) → (cookies_dict, extracted_at_timestamp)
        self._cache: dict[tuple[str, str | None], tuple[dict[str, str], float]] = {}

    def extract(
        self,
        browser: str,
        profile: str | None = None,
    ) -> dict[str, str]:
        """
        Extract TradingView session cookies from the named browser.

        Returns the cached result if it was extracted within ``COOKIE_CACHE_TTL``
        seconds. Otherwise reads from the browser's local cookie store.

        Args:
            browser: Browser to extract from. Must be ``"chrome"`` or
                ``"firefox"``.
            profile: Optional browser profile name (e.g. ``"Default"``,
                ``"Profile 2"``). If ``None``, the browser's default profile
                is used.

        Returns:
            Cookie name→value dict. Key cookies: ``sessionid``, ``csrftoken``,
            ``device_t``, ``tv_ecuid``.

        Raises:
            BrowserCookieError: If ``browser_cookie3`` is not installed,
                raises unexpectedly, or if ``sessionid`` is absent from
                the extracted cookies.
        """
        cache_key = (browser, profile)
        cached = self._cache.get(cache_key)
        if cached is not None:
            cookies_dict, extracted_at = cached
            age = time.monotonic() - extracted_at
            if age < COOKIE_CACHE_TTL:
                logger.debug(
                    "CookieProvider: returning cached cookies for browser=%r profile=%r "
                    "(age=%.0fs, ttl=%ds)",
                    browser,
                    profile,
                    age,
                    COOKIE_CACHE_TTL,
                )
                return cookies_dict

        cookies_dict = self._extract_from_browser(browser, profile)
        self._cache[cache_key] = (cookies_dict, time.monotonic())
        return cookies_dict

    def invalidate_cache(
        self,
        browser: str,
        profile: str | None = None,
    ) -> None:
        """
        Invalidate the cached cookies for the given browser/profile pair.

        The next call to :meth:`extract` for this pair will perform a fresh
        disk read, bypassing the TTL.

        Must be called when a WebSocket authentication error is detected —
        stale cookies must not be reused within the TTL window.

        Args:
            browser: Browser whose cache entry should be invalidated.
            profile: Profile whose cache entry should be invalidated.
                Use the same value passed to the original :meth:`extract` call.
        """
        cache_key = (browser, profile)
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.debug(
                "CookieProvider: cache invalidated for browser=%r profile=%r",
                browser,
                profile,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_from_browser(
        self,
        browser: str,
        profile: str | None,
    ) -> dict[str, str]:
        """
        Read cookies from the browser's local store via ``browser_cookie3``.

        Args:
            browser: ``"chrome"`` or ``"firefox"``.
            profile: Optional profile name.

        Returns:
            Flat name→value dict of all TradingView cookies.

        Raises:
            BrowserCookieError: On any extraction failure or missing
                ``sessionid``.
        """
        bc3 = _get_browser_cookie3()
        logger.debug(
            "CookieProvider: extracting cookies from browser=%r profile=%r",
            browser,
            profile,
        )

        try:
            if browser == "chrome":
                jar = bc3.chrome(domain_name=_TV_DOMAIN)
            elif browser == "firefox":
                jar = bc3.firefox(domain_name=_TV_DOMAIN)
            else:
                raise BrowserCookieError(
                    f"Unsupported browser: {browser!r}. Choose 'chrome' or 'firefox'."
                )
        except BrowserCookieError:
            raise
        except Exception as exc:
            raise BrowserCookieError(
                f"browser_cookie3 failed to extract cookies from {browser!r}: {exc}. "
                "Ensure the browser is installed and not currently writing to its database."
            ) from exc

        cookies_dict: dict[str, str] = {c.name: c.value for c in jar}

        if "sessionid" not in cookies_dict:
            raise BrowserCookieError(
                f"sessionid cookie not found in {browser!r} for tradingview.com. "
                "Please log in to TradingView in the browser and try again."
            )

        logger.info(
            "CookieProvider: extracted %d cookie(s) from browser=%r profile=%r",
            len(cookies_dict),
            browser,
            profile,
        )
        return cookies_dict
