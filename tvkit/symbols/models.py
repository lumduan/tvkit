"""
Pydantic models for the tvkit symbol normalization layer.
"""

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Regex constants — shared with normalizer.py via import from this module.
# normalizer.py imports from models.py, never the other way around.
# ---------------------------------------------------------------------------

#: Exchange component: uppercase letters, digits, underscores (e.g. NASDAQ, FX_IDC, CME_MINI).
EXCHANGE_PATTERN: str = r"^[A-Z0-9_]+$"

#: Ticker component: uppercase letters, digits, dots, exclamation marks
#: (e.g. AAPL, BRK.B, ES1!, BTCUSDT).
TICKER_PATTERN: str = r"^[A-Z0-9._!]+$"

#: Full canonical symbol: EXCHANGE:TICKER where each component satisfies the above patterns.
CANONICAL_PATTERN: str = r"^[A-Z0-9_]+:[A-Z0-9._!]+$"

_EXCHANGE_RE = re.compile(EXCHANGE_PATTERN)
_CANONICAL_RE = re.compile(CANONICAL_PATTERN)


class NormalizationType(str, Enum):
    """
    Classification of the primary transformation applied during symbol normalization.

    When multiple transformations are applied (e.g., strip + uppercase + dash-to-colon),
    only the **primary** transformation is recorded using the following precedence:

    1. ``WHITESPACE_STRIP``  — input had leading or trailing whitespace (highest priority)
    2. ``DASH_TO_COLON``     — a dash separator was converted to a colon
    3. ``UPPERCASE_ONLY``    — only case-folding was needed
    4. ``ALREADY_CANONICAL`` — input was already in exact canonical form (lowest priority)

    ``DEFAULT_EXCHANGE`` is a Phase 2 placeholder for bare-ticker resolution via
    ``NormalizationConfig.default_exchange``.
    """

    ALREADY_CANONICAL = "already_canonical"
    """Input was already in exact canonical EXCHANGE:SYMBOL form (uppercase, colon-separated)."""

    DASH_TO_COLON = "dash_to_colon"
    """A dash separator was converted to a colon (e.g., ``NASDAQ-AAPL`` → ``NASDAQ:AAPL``)."""

    UPPERCASE_ONLY = "uppercase_only"
    """Only case-folding was applied (e.g., ``nasdaq:aapl`` → ``NASDAQ:AAPL``)."""

    WHITESPACE_STRIP = "whitespace_strip"
    """Leading or trailing whitespace was stripped (e.g., ``'  NASDAQ:AAPL  '`` → ``NASDAQ:AAPL``)."""

    DEFAULT_EXCHANGE = "default_exchange"
    """Exchange prefix was supplied via ``NormalizationConfig.default_exchange``."""


class NormalizedSymbol(BaseModel):
    """
    Result model returned by ``normalize_symbol_detailed()``.

    Contains the canonical form of the symbol plus metadata about the primary transformation
    applied. This model is frozen (immutable) — all fields are set at construction time.

    **Validation contract:**

    - ``canonical`` must match ``^[A-Z0-9_]+:[A-Z0-9._!]+$``
    - ``exchange`` must match ``^[A-Z0-9_]+$`` and be non-empty
    - ``ticker`` must match ``^[A-Z0-9._!]+$`` and be non-empty
    - ``original`` must be non-empty and not whitespace-only
    - ``canonical`` must equal ``f"{exchange}:{ticker}"``

    Note on ``normalization_type`` consistency: this field records the *primary* transformation
    (see ``NormalizationType`` docstring for precedence). The model does not cross-validate
    ``normalization_type`` against ``original`` because the normalizer that constructs this
    object is the authoritative source of truth. Consumers should treat ``normalization_type``
    as informational metadata, not as a re-derivable invariant.

    Example:
        >>> result = normalize_symbol_detailed("NASDAQ-AAPL")
        >>> result.canonical          # "NASDAQ:AAPL"
        >>> result.exchange           # "NASDAQ"
        >>> result.ticker             # "AAPL"
        >>> result.original           # "NASDAQ-AAPL"
        >>> result.normalization_type # NormalizationType.DASH_TO_COLON
    """

    model_config = ConfigDict(frozen=True)

    canonical: str = Field(
        min_length=1,
        pattern=CANONICAL_PATTERN,
        description="Canonical TradingView symbol in EXCHANGE:SYMBOL format (uppercase).",
    )
    exchange: str = Field(
        min_length=1,
        pattern=EXCHANGE_PATTERN,
        description="Exchange component of the canonical symbol (e.g. 'NASDAQ', 'FX_IDC').",
    )
    ticker: str = Field(
        min_length=1,
        pattern=TICKER_PATTERN,
        description="Ticker component of the canonical symbol (e.g. 'AAPL', 'BRK.B', 'ES1!').",
    )
    original: str = Field(
        min_length=1,
        description="Original input string before any normalization was applied.",
    )
    normalization_type: NormalizationType = Field(
        description=(
            "Primary transformation applied during normalization. "
            "When multiple transforms are applied, the highest-priority one is recorded. "
            "See NormalizationType for the precedence order."
        )
    )

    @field_validator("original")
    @classmethod
    def _original_must_not_be_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("original must not be whitespace-only")
        return value

    @model_validator(mode="after")
    def _canonical_equals_exchange_colon_ticker(self) -> "NormalizedSymbol":
        """Enforce canonical == f'{exchange}:{ticker}'."""
        expected = f"{self.exchange}:{self.ticker}"
        if self.canonical != expected:
            raise ValueError(
                f"canonical '{self.canonical}' must equal '{{exchange}}:{{ticker}}' = '{expected}'"
            )
        return self


class NormalizationConfig(BaseSettings):
    """
    Configuration for symbol normalization behaviour.

    This class uses Pydantic Settings (``BaseSettings``) so that field values can be read
    from environment variables. The ``TVKIT_`` prefix maps each field to a corresponding
    environment variable:

    +------------------------------+----------------------------+
    | Field                        | Environment variable       |
    +==============================+============================+
    | ``default_exchange``         | ``TVKIT_DEFAULT_EXCHANGE`` |
    +------------------------------+----------------------------+
    | ``strip_whitespace``         | ``TVKIT_STRIP_WHITESPACE`` |
    +------------------------------+----------------------------+

    **Env var usage (Phase 2):**

    .. code-block:: bash

        export TVKIT_DEFAULT_EXCHANGE=NASDAQ

    .. code-block:: python

        from tvkit.symbols import NormalizationConfig, normalize_symbol

        config = NormalizationConfig()          # reads TVKIT_DEFAULT_EXCHANGE from env
        normalize_symbol("AAPL", config=config) # → "NASDAQ:AAPL"

    .. warning::

        ``TVKIT_DEFAULT_EXCHANGE`` is read **lazily at call time** — set the env var before
        calling ``normalize_symbol``. Passing an explicit ``config`` object is always the most
        predictable approach and is preferred for library code.

    **Behaviour with** ``default_exchange=None`` **(the default):** bare tickers (e.g.
    ``"AAPL"``) raise ``SymbolNormalizationError`` regardless of exchange presence.
    """

    model_config = SettingsConfigDict(env_prefix="TVKIT_", frozen=True)

    default_exchange: str | None = Field(
        default=None,
        description=(
            "Exchange to use when no prefix is present in the symbol (e.g. 'NASDAQ'). "
            "Must be a non-empty string containing only uppercase letters, digits, and underscores. "
            "Also readable from the TVKIT_DEFAULT_EXCHANGE environment variable."
        ),
    )
    strip_whitespace: bool = Field(
        default=True,
        description=(
            "Strip leading and trailing whitespace before normalization. "
            "Also readable from the TVKIT_STRIP_WHITESPACE environment variable."
        ),
    )

    @field_validator("default_exchange")
    @classmethod
    def _default_exchange_must_be_valid_when_set(cls, value: str | None) -> str | None:
        """When provided, default_exchange must be a valid uppercase exchange identifier."""
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("default_exchange must not be empty or whitespace-only when provided")
        if not _EXCHANGE_RE.match(stripped):
            raise ValueError(
                f"default_exchange '{value}' must contain only uppercase letters, "
                "digits, and underscores (e.g. 'NASDAQ', 'FX_IDC')"
            )
        return stripped
