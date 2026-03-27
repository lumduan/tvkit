"""TradingView profile fetch provider for tvkit.auth."""

import asyncio
import logging
import random
from typing import Any

import httpx

from tvkit.auth.exceptions import ProfileFetchError
from tvkit.auth.profile_parser import ProfileParser

__all__ = ["TokenProvider"]

logger: logging.Logger = logging.getLogger(__name__)

_HOMEPAGE_URL: str = "https://www.tradingview.com/"
_FETCH_TIMEOUT: float = 10.0

# Retry jitter constants for HTTP 5xx / timeout.
FETCH_RETRY_MIN_DELAY: float = 1.5
FETCH_RETRY_MAX_DELAY: float = 2.5

# Minimum expected length of a valid auth_token.
_MIN_TOKEN_LENGTH: int = 10


class TokenProvider:
    """
    Fetches the TradingView ``auth_token`` and user profile from the homepage.

    Issues an authenticated ``GET https://www.tradingview.com/`` using the
    supplied cookie jar. The response HTML is parsed by ``ProfileParser`` to
    extract the ``user`` object including ``auth_token``.

    Supports transparent re-extraction when a WebSocket auth error occurs.
    Uses an ``asyncio.Lock`` (double-checked locking pattern) to ensure only
    one concurrent re-extraction runs at a time — all other waiters receive
    the already-refreshed token.

    The provider holds the most recently fetched ``auth_token`` so that
    :meth:`get_valid_token` can return it without re-fetching on every call.

    Example::

        provider = TokenProvider()
        profile = await provider.fetch_profile(cookies)
        token = profile["auth_token"]
    """

    def __init__(self) -> None:
        self._token: str | None = None
        self._cookies: dict[str, str] | None = None
        self._refresh_lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_profile(
        self,
        cookies: dict[str, str],
    ) -> dict[str, Any]:
        """
        Retrieve the user profile and ``auth_token`` from the TradingView homepage.

        Issues ``GET https://www.tradingview.com/`` via ``httpx.AsyncClient``
        with the supplied cookie jar. The ``user`` object is extracted from the
        homepage bootstrap payload using ``ProfileParser`` (4-strategy fallback).

        Retries once on HTTP 5xx or ``httpx.TimeoutException`` with a random
        jitter delay of ``FETCH_RETRY_MIN_DELAY``–``FETCH_RETRY_MAX_DELAY``
        seconds. Defined by module-level constants to allow test overrides.

        After extraction, validates ``auth_token``: must be a non-empty string
        of at least ``_MIN_TOKEN_LENGTH`` characters.

        Args:
            cookies: Cookie name→value dict from ``CookieProvider``.
                Must include ``sessionid``.

        Returns:
            Parsed ``user`` profile dict from the TradingView homepage bootstrap.
            Includes at minimum ``id``, ``username``, ``auth_token``,
            ``pro_plan``, ``is_pro``, ``is_broker``, ``badges``.

        Raises:
            ProfileFetchError: If the homepage cannot be fetched after one
                retry, if the ``user`` object cannot be parsed, or if
                ``auth_token`` is missing or too short.
        """
        profile = await self._fetch_with_retry(cookies)
        self._cookies = cookies

        auth_token: Any = profile.get("auth_token")
        if not auth_token or len(str(auth_token)) < _MIN_TOKEN_LENGTH:
            raise ProfileFetchError(
                "Invalid auth_token extracted from TradingView homepage — "
                f"token is missing or too short (got: {str(auth_token)[:20]!r}). "
                "TradingView may have changed its bootstrap structure, or the "
                "session cookies may be expired."
            )

        self._token = str(auth_token)
        logger.info(
            "TokenProvider: auth_token obtained: %s... (len=%d)",
            self._token[:8],
            len(self._token),
        )
        return profile

    async def get_valid_token(
        self,
        cookies: dict[str, str],
    ) -> str:
        """
        Return a valid auth token, safe under concurrent access.

        Uses double-checked locking: after acquiring ``_refresh_lock``, checks
        whether the token was already refreshed by a competing coroutine before
        performing the actual re-extraction. This prevents N simultaneous expiries
        from triggering N cookie re-extractions.

        Args:
            cookies: Fresh cookie dict from ``CookieProvider`` (already
                invalidated before calling this method on WS auth error).

        Returns:
            A freshly-extracted ``auth_token``.

        Raises:
            ProfileFetchError: If re-extraction fails.
        """
        async with self._refresh_lock:
            # Double-check: another coroutine may have refreshed while we waited.
            if self._cookies is not None and cookies == self._cookies and self._token:
                logger.debug("TokenProvider: token already refreshed by a competing coroutine")
                return self._token
            profile = await self.fetch_profile(cookies)
            return str(profile["auth_token"])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_with_retry(
        self,
        cookies: dict[str, str],
    ) -> dict[str, Any]:
        """
        Fetch the TradingView homepage with one retry on HTTP 5xx or timeout.

        Args:
            cookies: Cookie dict to send with the request.

        Returns:
            Parsed ``user`` profile dict.

        Raises:
            ProfileFetchError: After exhausting retries.
        """
        last_error: Exception | None = None

        for attempt in range(2):
            try:
                return await self._do_fetch(cookies)
            except ProfileFetchError as exc:
                # Structural parse errors are not retryable — surface immediately.
                raise exc from None
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt == 0:
                    jitter = random.uniform(FETCH_RETRY_MIN_DELAY, FETCH_RETRY_MAX_DELAY)
                    logger.warning(
                        "TokenProvider: profile fetch failed (%s); retrying in %.1f s",
                        type(exc).__name__,
                        jitter,
                    )
                    await asyncio.sleep(jitter)

        raise ProfileFetchError(
            f"Failed to fetch TradingView profile after one retry: {last_error}"
        ) from last_error

    async def _do_fetch(
        self,
        cookies: dict[str, str],
    ) -> dict[str, Any]:
        """
        Issue a single authenticated GET to the TradingView homepage.

        Args:
            cookies: Cookie dict to send with the request.

        Returns:
            Parsed ``user`` profile dict.

        Raises:
            ProfileFetchError: If the user object cannot be parsed.
            httpx.TimeoutException: On connect or read timeout.
            httpx.HTTPStatusError: On HTTP 5xx responses.
        """
        logger.debug("TokenProvider: fetching authenticated TradingView homepage")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_FETCH_TIMEOUT),
            cookies=cookies,
            follow_redirects=True,
        ) as client:
            response = await client.get(_HOMEPAGE_URL)

        if response.status_code >= 500:
            response.raise_for_status()

        html: str = response.text
        profile = ProfileParser.parse(html)
        return profile
