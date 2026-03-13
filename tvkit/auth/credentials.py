"""TradingView credential models for tvkit.auth."""

from dataclasses import dataclass, field

__all__ = ["TradingViewCredentials"]


@dataclass
class TradingViewCredentials:
    """
    Holds the authentication credentials for a TradingView session.

    Exactly one of the following modes must be used:

    - **Anonymous** (default): all fields empty — uses ``"unauthorized_user_token"``.
    - **Username + password**: provide both ``username`` and ``password``; tvkit
      performs the full Stage 0→1→2 login flow to obtain the ``auth_token``.
    - **Direct token**: provide ``auth_token`` only — bypasses login entirely.
      The caller is responsible for token freshness in this mode.

    Args:
        username: TradingView account username. Must be paired with ``password``.
        password: TradingView account password. Must be paired with ``username``.
            Hidden from ``repr`` to prevent credential leakage in logs.
        auth_token: Pre-obtained TradingView auth token. Mutually exclusive with
            ``username`` + ``password``. Hidden from ``repr``.

    Raises:
        ValueError: If both ``(username/password)`` and ``auth_token`` are provided,
            or if only one of ``username``/``password`` is given.

    Example:
        >>> creds = TradingViewCredentials(username="alice", password="s3cr3t")
        >>> creds.uses_credentials
        True
        >>> creds.is_anonymous
        False
    """

    username: str = ""
    password: str = field(default="", repr=False)
    auth_token: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        has_creds = bool(self.username or self.password)
        has_token = bool(self.auth_token)

        if has_creds and has_token:
            raise ValueError("Provide (username + password) OR auth_token, not both.")
        if bool(self.username) != bool(self.password):
            raise ValueError("username and password must be provided together.")

    @property
    def is_anonymous(self) -> bool:
        """Return ``True`` if no credentials or token are provided."""
        return not self.username and not self.auth_token

    @property
    def uses_direct_token(self) -> bool:
        """Return ``True`` if a pre-obtained ``auth_token`` was provided."""
        return bool(self.auth_token)

    @property
    def uses_credentials(self) -> bool:
        """Return ``True`` if username + password were provided for login."""
        return bool(self.username and self.password)
