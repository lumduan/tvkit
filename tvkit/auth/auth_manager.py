"""TradingView authentication manager for tvkit.auth."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from tvkit.auth.capability_detector import CapabilityDetector
from tvkit.auth.cookie_provider import CookieProvider
from tvkit.auth.credentials import TradingViewCredentials
from tvkit.auth.models import TradingViewAccount
from tvkit.auth.token_provider import TokenProvider

if TYPE_CHECKING:
    from websockets.asyncio.client import ClientConnection

__all__ = ["AuthManager"]

logger: logging.Logger = logging.getLogger(__name__)

_ANONYMOUS_TOKEN: str = "unauthorized_user_token"


class AuthManager:
    """
    Async context manager that orchestrates TradingView authentication.

    Supports three authentication modes, determined by ``TradingViewCredentials``:

    - **Anonymous**: ``auth_token = "unauthorized_user_token"``, ``account = None``,
      no capability probe launched. Full backward compatibility.
    - **Direct token**: ``auth_token = credentials.auth_token``, ``account = None``,
      no capability probe launched. Caller is responsible for token refresh.
    - **Browser / cookie dict**: extracts or receives session cookies →
      issues authenticated ``GET /`` via ``TokenProvider`` → populates
      ``TradingViewAccount`` → launches the background capability probe task.

    ``CookieProvider`` and ``TokenProvider`` are held alive for the full
    lifetime of the context manager so that token re-extraction can be
    triggered by ``ConnectionService`` (Phase 3+) when a WebSocket auth
    error occurs.

    Args:
        credentials: Authentication credentials. Defaults to anonymous mode.

    Example::

        # Anonymous (unchanged behaviour)
        async with AuthManager() as auth:
            token = auth.auth_token  # "unauthorized_user_token"
            account = auth.account   # None

        # Browser cookie extraction
        from tvkit.auth import TradingViewCredentials
        creds = TradingViewCredentials(browser="chrome")
        async with AuthManager(creds) as auth:
            token = auth.auth_token      # real TradingView auth token
            account = auth.account       # TradingViewAccount(tier="premium", ...)

        # Direct token injection
        creds = TradingViewCredentials(auth_token="tv_auth_token_here")
        async with AuthManager(creds) as auth:
            token = auth.auth_token  # the injected token
    """

    def __init__(
        self,
        credentials: TradingViewCredentials | None = None,
    ) -> None:
        self._credentials: TradingViewCredentials = credentials or TradingViewCredentials()
        self._auth_token: str | None = None
        self._account: TradingViewAccount | None = None
        self._cookie_provider: CookieProvider | None = None
        self._token_provider: TokenProvider | None = None
        self._probe_task: asyncio.Task[None] | None = None
        self._probe_ws: ClientConnection | None = None  # reserved for Phase 5

    async def __aenter__(self) -> "AuthManager":
        """
        Authenticate and return the manager.

        For browser / cookie dict mode, extracts cookies, fetches the
        TradingView homepage to obtain ``auth_token`` + profile, estimates
        capabilities from the plan, and launches the background probe task.

        Returns:
            This ``AuthManager`` instance.

        Raises:
            BrowserCookieError: If browser cookie extraction fails.
            ProfileFetchError: If the TradingView user profile cannot be
                extracted from the homepage bootstrap.
        """
        creds = self._credentials

        if creds.is_anonymous:
            logger.debug("AuthManager: anonymous mode — using unauthorized_user_token")
            self._auth_token = _ANONYMOUS_TOKEN

        elif creds.uses_direct_token:
            logger.debug("AuthManager: direct-token mode — skipping cookie extraction")
            self._auth_token = creds.auth_token

        else:
            # Browser or cookie-dict mode: extract/use cookies → fetch profile
            await self._authenticate_with_cookies(creds)

        # Launch background probe only when account is known.
        # Anonymous and direct-token modes have no plan info to probe.
        if self._account is not None:
            self._probe_task = asyncio.create_task(
                self._probe_capabilities(),
                name="tvkit-capability-probe",
            )
            self._probe_task.add_done_callback(self._handle_probe_done)

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """
        Cancel the background probe task.

        Cleanup runs in all exit paths (normal, exception, cancellation).
        The probe WebSocket (``_probe_ws``) is closed before task cancellation
        to unblock any pending ``recv()`` awaitable.
        """
        if self._probe_task is not None and not self._probe_task.done():
            if self._probe_ws is not None:
                try:
                    await self._probe_ws.close()
                except Exception:
                    pass
            self._probe_task.cancel()
            try:
                await self._probe_task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Internal authentication helpers
    # ------------------------------------------------------------------

    async def _authenticate_with_cookies(
        self,
        creds: TradingViewCredentials,
    ) -> None:
        """
        Execute cookie extraction (or use provided dict) then fetch the profile.

        Args:
            creds: Credentials in browser or cookie-dict mode.
        """
        # Obtain cookie dict — either from browser extraction or directly provided.
        if creds.uses_browser:
            logger.info(
                "AuthManager: browser mode — extracting cookies from browser=%r profile=%r",
                creds.browser,
                creds.browser_profile,
            )
            self._cookie_provider = CookieProvider()
            cookies = self._cookie_provider.extract(
                browser=str(creds.browser),
                profile=creds.browser_profile,
            )
        else:
            # cookie-dict mode — caller supplies the dict directly
            logger.info("AuthManager: cookie-dict mode — using provided cookie dict")
            cookies = dict(creds.cookies or {})

        # Fetch profile from the authenticated TradingView homepage.
        self._token_provider = TokenProvider()
        profile = await self._token_provider.fetch_profile(cookies)

        self._auth_token = str(profile["auth_token"])

        # Estimate capabilities from the plan and build the account model.
        max_bars, tier = CapabilityDetector.estimate_from_plan(
            pro_plan=profile.get("pro_plan", ""),  # type: ignore[arg-type]
            badges=profile.get("badges", []),  # type: ignore[arg-type]
        )
        self._account = TradingViewAccount.from_profile(
            profile=profile,
            max_bars=max_bars,
            tier=tier,
        )
        logger.info(
            "AuthManager: authenticated as %r (tier=%s, estimated_max_bars=%d)",
            self._account,
            self._account.tier,
            self._account.estimated_max_bars,
        )

    # ------------------------------------------------------------------
    # Background probe (Phase 5 stub)
    # ------------------------------------------------------------------

    async def _probe_capabilities(self) -> None:
        """
        Background capability probe — Phase 5 stub.

        Will be replaced in Phase 5 with a dedicated short-lived WebSocket
        connection that requests 50,000 daily bars (adaptive: 50k → 40k → 20k)
        and records the server's truncation point as the confirmed ``max_bars``.
        """
        account = self._account
        if account is None:
            return
        try:
            logger.debug(
                "Capability probe not yet implemented (Phase 5 stub). "
                "Retaining plan-based estimate: max_bars=%d",
                account.estimated_max_bars,
            )
        except Exception:
            logger.exception("Capability probe failed unexpectedly")

    def _handle_probe_done(self, task: asyncio.Task[None]) -> None:
        """
        Done-callback for the background capability probe task.

        Retrieves the task result to surface any unhandled exception that
        slipped past the ``try/except`` inside ``_probe_capabilities``,
        preventing the "Task exception was never retrieved" asyncio warning.
        """
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("Capability probe raised an unexpected exception", exc_info=exc)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def auth_token(self) -> str:
        """
        The current TradingView ``auth_token`` for WebSocket authentication.

        Raises:
            AssertionError: If accessed before entering the async context manager.
        """
        assert self._auth_token is not None, (
            "auth_token is not set — use 'async with AuthManager(...) as auth' "
            "before accessing auth.auth_token"
        )
        return self._auth_token

    @property
    def account(self) -> TradingViewAccount | None:
        """
        The authenticated account profile, or ``None`` in anonymous / direct-token mode.
        """
        return self._account

    @property
    def cookie_provider(self) -> CookieProvider | None:
        """
        The ``CookieProvider`` instance, or ``None`` in non-browser mode.

        Exposed for ``ConnectionService`` (Phase 3+) to call
        ``invalidate_cache()`` before re-extraction on a WebSocket auth error.
        """
        return self._cookie_provider

    @property
    def token_provider(self) -> TokenProvider | None:
        """
        The ``TokenProvider`` instance, or ``None`` in anonymous / direct-token mode.

        Exposed for ``ConnectionService`` (Phase 3+) to call
        ``get_valid_token()`` when a WebSocket auth error occurs.
        """
        return self._token_provider
