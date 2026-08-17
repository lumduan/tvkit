"""WebSocket quote-snapshot transport for :mod:`tvkit.api.fundamentals`.

Thin wrapper over the proven chart WebSocket primitives. It runs a **one-shot** quote snapshot:
open the socket, send the quote verbs, collect ``qsd`` frames until ``quote_completed``, return
the merged field dict per symbol.

Reuses (see ``docs/development/architecture-decisions.md``):
  * :class:`tvkit.api.chart.services.connection_service.ConnectionService` — connect, the
    ``~m~len~m~`` framing, heartbeat echo, auth-error detection, reconnect/backoff.
  * :class:`tvkit.api.chart.services.message_service.MessageService` — session-id generation and
    the outbound send callable.
  * :class:`tvkit.api.chart.models.QuoteSymbolData` / ``QuoteCompletedMessage`` — frame parsing.

It does **not** use ``ConnectionService.initialize_sessions`` (which also creates a chart session
and hibernates quotes) — it sends the quote verbs directly with the fundamentals field list.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from tvkit.api.chart.exceptions import AuthError, StreamConnectionError
from tvkit.api.chart.models import QuoteCompletedMessage, QuoteSymbolData
from tvkit.api.chart.services.connection_service import ConnectionService
from tvkit.api.chart.services.message_service import MessageService
from tvkit.api.fundamentals.exceptions import (
    FundamentalsAuthError,
    FundamentalsConnectionError,
    FundamentalsTimeoutError,
)

__all__ = ["QuoteSnapshotTransport", "STANDARD_WS_URL"]

logger: logging.Logger = logging.getLogger(__name__)

# The chart data socket; fundamentals quote fields are served here (findings.md §1).
STANDARD_WS_URL: str = "wss://data.tradingview.com/socket.io/websocket?from=chart%2F"


class QuoteSnapshotTransport:
    """Runs one-shot quote-field snapshots over the TradingView WebSocket.

    Args:
        auth_token: Token for ``set_auth_token``. Anonymous default works for fundamentals.
        language: Locale sent via ``set_locale`` — controls segment-label localization.
        ws_url: Override the WebSocket endpoint (tests / prodata).
        timeout: Seconds to wait for every requested symbol to ``quote_completed``.
    """

    def __init__(
        self,
        auth_token: str = "unauthorized_user_token",
        language: str = "en",
        ws_url: str = STANDARD_WS_URL,
        timeout: float = 30.0,
    ) -> None:
        self._auth_token = auth_token
        self._language = language
        self._ws_url = ws_url
        self._timeout = timeout
        self._connection: ConnectionService | None = None
        self._message: MessageService | None = None

    async def connect(self) -> None:
        """Open the WebSocket connection."""
        connection = ConnectionService(
            ws_url=self._ws_url,
            auth_token=self._auth_token,
            on_reconnect=None,
        )
        try:
            await connection.connect()
        except StreamConnectionError as exc:
            raise FundamentalsConnectionError(str(exc)) from exc
        if connection.ws is None:
            raise FundamentalsConnectionError("WebSocket connection was not established.")
        self._connection = connection
        self._message = MessageService(connection.ws)

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._message = None

    async def snapshot(self, symbols: list[str], fields: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch ``fields`` for ``symbols`` and return ``{symbol: merged_v_dict}``.

        Sends the quote verbs, then merges every ``qsd`` ``v`` dict per symbol until each symbol
        reports ``quote_completed`` (or the timeout elapses).

        Raises:
            FundamentalsConnectionError: If not connected, or the socket drops.
            FundamentalsAuthError: If the server rejects the auth token.
            FundamentalsTimeoutError: If not every symbol completes before ``timeout``.
        """
        if self._connection is None or self._message is None:
            raise FundamentalsConnectionError("Transport is not connected — call connect() first.")

        session = self._message.generate_session(prefix="qs_")
        send = self._message.get_send_message_callable()
        await send("set_auth_token", [self._auth_token])
        await send("set_locale", [self._language, "US"])
        await send("quote_create_session", [session])
        await send("quote_set_fields", [session, *fields])
        await send("quote_add_symbols", [session, *symbols])
        await send("quote_fast_symbols", [session, *symbols])

        merged: dict[str, dict[str, Any]] = {sym: {} for sym in symbols}
        remaining: set[str] = set(symbols)

        try:
            async with asyncio.timeout(self._timeout):
                async for data in self._connection.get_data_stream():
                    kind = data.get("m")
                    if kind == "qsd":
                        quote = QuoteSymbolData.model_validate(data)
                        if quote.session_id != session:  # ignore other snapshots' frames
                            continue
                        name = quote.quote_data.get("n")
                        if name in merged and isinstance(quote.symbol_info, dict):
                            merged[name].update(quote.symbol_info)
                    elif kind == "quote_completed":
                        done = QuoteCompletedMessage.model_validate(data)
                        if done.session_id != session:  # stale completion from a prior call
                            continue
                        remaining.discard(done.symbol)
                        if not remaining:
                            break
        except AuthError as exc:
            raise FundamentalsAuthError(str(exc)) from exc
        except StreamConnectionError as exc:
            raise FundamentalsConnectionError(str(exc)) from exc
        except TimeoutError as exc:
            if all(merged[s] for s in symbols):
                logger.debug("snapshot timed out after data arrived for all symbols; returning")
            else:
                missing = [s for s in symbols if not merged[s]]
                raise FundamentalsTimeoutError(
                    f"quote_completed not received for {missing} within {self._timeout}s"
                ) from exc
        return merged
