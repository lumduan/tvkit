"""TradingView HTTP authentication provider for tvkit.auth."""

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any

from tvkit.auth.exceptions import AuthenticationError, ProfileFetchError
from tvkit.auth.profile_parser import ProfileParser

try:
    from curl_cffi import CurlMime  # type: ignore[import-untyped]
    from curl_cffi.requests import AsyncSession  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    CurlMime = None  # type: ignore[assignment,misc]
    AsyncSession = None  # type: ignore[assignment,misc]

__all__ = ["LoginResult", "TokenProvider"]

logger: logging.Logger = logging.getLogger(__name__)

_BASE_URL: str = "https://www.tradingview.com"
_LOGIN_URL: str = f"{_BASE_URL}/accounts/signin/"
_LOGIN_TIMEOUT: float = 30.0


@dataclass
class LoginResult:
    """
    Result of a successful TradingView login.

    Attributes:
        auth_token: The ``auth_token`` extracted from the Stage 2 homepage bootstrap.
        user_profile: The full parsed ``user`` profile dict from the homepage.
    """

    auth_token: str
    user_profile: dict[str, Any]


class TokenProvider:
    """
    Manages the TradingView HTTP login flow and provides a valid ``auth_token``.

    Implements a 2-stage login protocol:

    - **Stage 1** — ``POST /accounts/signin/`` with ``multipart/form-data``
      credentials. No CSRF token is required.
    - **Stage 2** — Authenticated ``GET /`` to extract ``auth_token`` and user
      profile from the homepage bootstrap payload.

    Must be used as an ``async with`` context manager. The ``curl-cffi``
    ``AsyncSession`` is opened in ``__aenter__`` and closed in ``__aexit__``.
    ``AuthManager`` holds the provider alive for its full lifetime so that
    ``handle_401()`` and ``handle_403()`` can re-login on token expiry.

    Args:
        username: TradingView account username.
        password: TradingView account password.
    """

    def __init__(self, username: str, password: str) -> None:
        self._username: str = username
        self._password: str = password
        self._session: Any = None  # curl_cffi.requests.AsyncSession; opened in __aenter__
        self._relogin_in_progress: bool = False

    async def __aenter__(self) -> "TokenProvider":
        """Open the curl-cffi AsyncSession with Chrome TLS fingerprint."""
        if AsyncSession is None:  # pragma: no cover
            raise ImportError(
                "curl-cffi is required for TradingView authentication. "
                "Install it with: uv add curl-cffi"
            )
        self._session = AsyncSession(impersonate="chrome110")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Close the curl-cffi AsyncSession."""
        await self.close()

    # ------------------------------------------------------------------
    # Lifecycle helpers (preferred over calling __aenter__/__aexit__ directly)
    # ------------------------------------------------------------------

    async def open(self) -> None:
        """
        Open the curl-cffi ``AsyncSession``.

        Equivalent to entering the async context manager. Prefer this over
        calling ``__aenter__()`` directly when ``AuthManager`` needs to own
        the provider lifecycle across multiple method calls.

        Raises:
            ImportError: If ``curl-cffi`` is not installed.
        """
        await self.__aenter__()

    async def close(self) -> None:
        """
        Close the curl-cffi ``AsyncSession``.

        Equivalent to exiting the async context manager. Safe to call multiple
        times; subsequent calls are no-ops if the session is already closed.
        """
        if self._session is not None:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Public login methods
    # ------------------------------------------------------------------

    async def login(self) -> LoginResult:
        """
        Execute the Stage 1 → Stage 2 login flow.

        Stage 1 POSTs credentials to ``/accounts/signin/`` (no CSRF required).
        Stage 2 fetches the authenticated homepage to extract ``auth_token``.

        Returns:
            A ``LoginResult`` containing ``auth_token`` and ``user_profile``.

        Raises:
            RuntimeError: If called before entering the async context manager.
            AuthenticationError: If credentials are rejected (HTTP 401),
                session is forbidden (HTTP 403), or login times out after one retry.
            ProfileFetchError: If the homepage bootstrap payload cannot be parsed
                or the user profile is missing required fields.
        """
        self._require_session("login")
        await self._stage1_login_with_retry()
        return await self._stage2_get_login_result()

    async def handle_401(self) -> LoginResult:
        """
        Handle an HTTP 401 auth error by re-running Stage 1 + Stage 2.

        Raises ``AuthenticationError`` immediately if a re-login is already in
        progress (re-login loop prevention).

        Returns:
            A fresh ``LoginResult`` with the new ``auth_token``.

        Raises:
            RuntimeError: If called before entering the async context manager.
            AuthenticationError: If ``_relogin_in_progress`` is already ``True``
                (loop detection), or if Stage 1 returns HTTP 401/403/timeout.
            ProfileFetchError: If Stage 2 profile extraction fails.
        """
        self._require_session("handle_401")
        if self._relogin_in_progress:
            raise AuthenticationError(
                "Re-login loop detected — HTTP 401 persisted after re-login attempt. "
                "Check that credentials are still valid."
            )
        self._relogin_in_progress = True
        try:
            await self._stage1_login_with_retry()
            return await self._stage2_get_login_result()
        finally:
            self._relogin_in_progress = False

    async def handle_403(self) -> LoginResult:
        """
        Handle an HTTP 403 session expiry by executing the full Stage 1 + 2 flow.

        Returns:
            A fresh ``LoginResult`` with the new ``auth_token``.

        Raises:
            RuntimeError: If called before entering the async context manager.
            AuthenticationError: On HTTP 401/403, or timeout.
            ProfileFetchError: On Stage 2 profile extraction failure.
        """
        self._require_session("handle_403")
        return await self.login()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_session(self, method_name: str) -> None:
        """Guard against calls made before entering the async context manager."""
        if self._session is None:
            raise RuntimeError(
                f"TokenProvider.{method_name}() called before entering async context manager. "
                "Use: async with TokenProvider(...) as provider: ..."
            )

    async def _stage1_login_with_retry(self) -> None:
        """
        Stage 1 with a single timeout retry (jitter 1.5–2.5 s).

        Raises:
            AuthenticationError: On HTTP 401/403/4xx or timeout after one retry.
        """
        for attempt in range(2):
            try:
                await self._stage1_login()
                return
            except TimeoutError:
                if attempt == 0:
                    jitter = random.uniform(1.5, 2.5)
                    logger.warning("Stage 1 login timed out; retrying in %.1f s", jitter)
                    await asyncio.sleep(jitter)
                else:
                    raise AuthenticationError(
                        "TradingView login timed out after one retry. "
                        "Check your network connection."
                    ) from None

    async def _stage1_login(self) -> None:
        """
        Stage 1: POST /accounts/signin/ with multipart/form-data credentials.

        TradingView does not require a CSRF token for this endpoint when using
        a browser-fingerprinted TLS session (curl-cffi impersonate).

        Raises:
            AuthenticationError: On HTTP 401 (wrong credentials), HTTP 403
                (session expired), or other HTTP 4xx/5xx errors.
            TimeoutError: If the request exceeds ``_LOGIN_TIMEOUT``.
        """
        logger.debug("Stage 1: posting login credentials to TradingView")
        if CurlMime is None:  # pragma: no cover
            raise ImportError("curl-cffi is required for TradingView authentication.")
        form = CurlMime()
        form.addpart("username", data=self._username.encode())
        form.addpart("password", data=self._password.encode())
        form.addpart("remember", data=b"true")
        response = await self._session.post(
            _LOGIN_URL,
            multipart=form,
            headers={
                "Referer": _BASE_URL + "/",
                "x-language": "en",
                "x-requested-with": "XMLHttpRequest",
            },
            timeout=_LOGIN_TIMEOUT,
        )

        status = response.status_code
        if status == 401:
            raise AuthenticationError(
                "TradingView returned HTTP 401 — invalid username or password."
            )
        if status == 403:
            raise AuthenticationError(
                "TradingView returned HTTP 403 — session expired. "
                "Call handle_403() to perform a full re-login."
            )
        if status >= 400:
            raise AuthenticationError(f"TradingView login failed with HTTP {status}.")

        # Check for application-level errors returned with HTTP 200 (e.g. CAPTCHA)
        try:
            body = response.json()
            if isinstance(body, dict) and body.get("error"):
                raise AuthenticationError(f"TradingView login rejected: {body['error']}")
        except (ValueError, AttributeError):
            pass  # Non-JSON response is fine — Stage 2 will validate auth state

        logger.debug("Stage 1: login POST succeeded (HTTP %d)", status)

    async def _stage2_get_login_result(self) -> LoginResult:
        """
        Stage 2: GET / (authenticated) and extract auth_token + user profile.

        Returns:
            ``LoginResult`` with ``auth_token`` and ``user_profile``.

        Raises:
            ProfileFetchError: If the homepage cannot be parsed or ``auth_token``
                is missing from the profile.
        """
        logger.debug("Stage 2: fetching authenticated TradingView homepage")
        response = await self._session.get(_BASE_URL, timeout=_LOGIN_TIMEOUT)
        html: str = response.text

        profile = ProfileParser.parse(html)

        auth_token: str | None = profile.get("auth_token")
        if not auth_token:
            raise ProfileFetchError(
                "auth_token field is missing or empty in the TradingView user profile. "
                "The authenticated homepage returned a profile without an auth token."
            )

        logger.info(
            "Stage 2: auth_token obtained: %s... (len=%d)",
            auth_token[:8],
            len(auth_token),
        )
        return LoginResult(auth_token=auth_token, user_profile=profile)
