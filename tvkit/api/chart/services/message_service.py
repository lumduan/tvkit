"""Message service for constructing and sending WebSocket messages."""

import json
import logging
import secrets
import string
from typing import Any, Awaitable, Callable

from websockets import ClientConnection
from websockets.exceptions import ConnectionClosed, WebSocketException


class MessageService:
    """
    Service for constructing and sending WebSocket messages to TradingView.

    This service handles the message protocol, formatting, and sending
    operations for TradingView WebSocket communication.
    """

    def __init__(self, ws: ClientConnection) -> None:
        """
        Initialize the message service.

        Args:
            ws: The WebSocket connection to use for sending messages
        """
        self.ws: ClientConnection = ws

    def generate_session(self, prefix: str) -> str:
        """
        Generates a random session identifier.

        Args:
            prefix: The prefix to prepend to the random string.

        Returns:
            A session identifier consisting of the prefix and a random string.
        """
        random_string: str = "".join(
            secrets.choice(string.ascii_lowercase) for _ in range(12)
        )
        return prefix + random_string

    def prepend_header(self, message: str) -> str:
        """
        Prepends the message with a header indicating its length.

        Args:
            message: The message to be sent.

        Returns:
            The message prefixed with its length.
        """
        message_length: int = len(message)
        return f"~m~{message_length}~m~{message}"

    def construct_message(self, func: str, param_list: list[Any]) -> str:
        """
        Constructs a message in JSON format.

        Args:
            func: The function name to be called.
            param_list: The list of parameters for the function.

        Returns:
            The constructed JSON message.
        """
        return json.dumps({"m": func, "p": param_list}, separators=(",", ":"))

    def create_message(self, func: str, param_list: list[Any]) -> str:
        """
        Creates a complete message with a header and a JSON body.

        Args:
            func: The function name to be called.
            param_list: The list of parameters for the function.

        Returns:
            The complete message ready to be sent.
        """
        return self.prepend_header(self.construct_message(func, param_list))

    async def send_message(self, func: str, args: list[Any]) -> None:
        """
        Sends a message to the WebSocket server.

        Args:
            func: The function name to be called.
            args: The arguments for the function.

        Raises:
            RuntimeError: If WebSocket connection is not established
            ConnectionClosed: If WebSocket connection is closed
            WebSocketException: If sending fails
        """
        if not self.ws:
            raise RuntimeError(
                "WebSocket connection not established. Call _connect() first."
            )

        message: str = self.create_message(func, args)
        logging.debug("Sending message: %s", message)

        try:
            await self.ws.send(message)
        except ConnectionClosed as e:
            logging.error("WebSocket connection closed while sending message: %s", e)
            raise
        except WebSocketException as e:
            logging.error("Failed to send message: %s", e)
            raise

    def get_send_message_callable(self) -> Callable[[str, list[Any]], Awaitable[None]]:
        """
        Returns a callable that can be passed to other services for sending messages.

        Returns:
            A callable that sends messages through this service
        """
        return self.send_message
