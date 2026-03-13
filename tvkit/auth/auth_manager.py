"""TradingView authentication manager for tvkit.auth."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from tvkit.auth.capability_detector import CapabilityDetector
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

    Supports three authentication modes (determined by ``TradingViewCredentials``):

    - **Anonymous**: ``auth_token = "unauthorized_user_token"``, ``account = None``,
      no capability probe launched.
    - **Direct token**: ``auth_token = credentials.auth_token``, ``account = None``,
      no capability probe launched.
    - **Credentials** (username + password): runs the Stage 0→1→2 login flow via
      ``TokenProvider``, populates ``TradingViewAccount``, and launches the
      background capability probe task (Phase 5 stub).

    The ``TokenProvider`` is held alive for the full lifetime of the context
    manager so that ``token_provider.handle_401()`` and ``handle_403()`` can
    be called by ``ConnectionService`` (Phase 6–8) when auth errors occur on
    a live WebSocket session.

    Args:
        credentials: Authentication credentials. Defaults to anonymous mode.

    Example:
        >>> async with AuthManager(TradingViewCredentials()) as auth:
        ...     token = auth.auth_token  # "unauthorized_user_token"
        ...     account = auth.account   # None

        >>> creds = TradingViewCredentials(username="alice", password="s3cr3t")
        >>> async with AuthManager(creds) as auth:
        ...     token = auth.auth_token     # real token
        ...     account = auth.account      # TradingViewAccount(...)
        ...     provider = auth.token_provider  # for Phase 6-8 token refresh
    """

    def __init__(
        self,
        credentials: TradingViewCredentials | None = None,
    ) -> None:
        self._credentials: TradingViewCredentials = credentials or TradingViewCredentials()
        self._auth_token: str | None = None
        self._account: TradingViewAccount | None = None
        self._provider: TokenProvider | None = None
        self._probe_task: asyncio.Task[None] | None = None
        self._probe_ws: ClientConnection | None = None  # reserved for Phase 5

    async def __aenter__(self) -> "AuthManager":
        """
        Authenticate and return the manager.

        For credentials mode, runs the full login flow, estimates capabilities,
        and launches the background probe task.

        Returns:
            This ``AuthManager`` instance.

        Raises:
            AuthenticationError: If login fails.
            ProfileFetchError: If the user profile cannot be extracted.
        """
        if self._credentials.is_anonymous:
            logger.debug("AuthManager: anonymous mode — using unauthorized_user_token")
            self._auth_token = _ANONYMOUS_TOKEN

        elif self._credentials.uses_direct_token:
            logger.debug("AuthManager: direct-token mode — skipping login flow")
            self._auth_token = self._credentials.auth_token

        else:
            # Credentials mode: Stage 0 + 1 + 2 login, capability estimate, probe launch
            logger.info("AuthManager: credentials mode — starting login flow")
            logger.debug(
                "AuthManager: logging in as '%s'",
                self._credentials.username,
            )
            self._provider = TokenProvider(
                username=self._credentials.username,
                password=self._credentials.password,
            )
            await self._provider.open()

            result = await self._provider.login()
            self._auth_token = result.auth_token

            max_bars, tier = CapabilityDetector.estimate_from_plan(
                pro_plan=result.user_profile.get("pro_plan", ""),
                badges=result.user_profile.get("badges", []),
            )
            self._account = TradingViewAccount.from_profile(
                profile=result.user_profile,
                max_bars=max_bars,
                tier=tier,
            )
            logger.info(
                "AuthManager: logged in as '%s' (tier=%s, estimated_max_bars=%d)",
                self._account.username,
                self._account.tier,
                self._account.estimated_max_bars,
            )

        # Launch background probe only when account is known (credentials mode).
        # Anonymous and direct-token modes have no plan information to probe.
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
        Cancel the background probe task and close the ``TokenProvider`` session.

        Cleanup is performed in all exit paths (normal, exception, cancellation).
        The probe WebSocket (``_probe_ws``) is closed before task cancellation
        to unblock any pending ``recv()`` awaitable (Phase 5).
        """
        # Step 1: cancel probe task (if still running)
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

        # Step 2: close the persistent TokenProvider session
        if self._provider is not None:
            await self._provider.close()
            self._provider = None

    async def _probe_capabilities(self) -> None:
        """
        Background capability probe — Phase 5 stub.

        Will be replaced in Phase 5 with a dedicated short-lived WebSocket
        connection that requests 100,000 daily bars and records the server's
        truncation point as the confirmed ``max_bars``.
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
            logger.exception("Capability probe failed")

    def _handle_probe_done(self, task: asyncio.Task[None]) -> None:
        """
        Done-callback for the background capability probe task.

        Retrieves the task result to surface any unhandled exception that
        slipped past the ``try/except`` inside ``_probe_capabilities``,
        preventing the "Task exception was never retrieved" warning.
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
            RuntimeError: If accessed before entering the async context manager.
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
    def token_provider(self) -> TokenProvider | None:
        """
        The persistent ``TokenProvider`` session, or ``None`` in non-credentials mode.

        Exposed for ``ConnectionService`` (Phase 6–8) to call ``handle_401()``
        or ``handle_403()`` when auth errors occur on a live WebSocket session.
        """
        return self._provider
