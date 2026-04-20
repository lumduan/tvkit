"""Pydantic models for tvkit.batch batch download operations."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, Field, SecretStr, computed_field, field_validator, model_validator

from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.chart.utils import validate_interval

__all__ = [
    "BatchDownloadRequest",
    "BatchDownloadSummary",
    "ErrorInfo",
    "SymbolResult",
]

_VALID_BROWSERS: frozenset[str] = frozenset({"chrome", "firefox"})


def _to_utc_aware(dt: datetime) -> datetime:
    """Return a UTC-aware datetime. Naive datetimes are assumed to be UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class ErrorInfo(BaseModel):
    """Structured error record for a failed symbol fetch.

    Populated on the attempt where the terminal error occurred — either the last
    retryable attempt or the first non-retryable attempt.
    """

    message: str = Field(description="Human-readable error message")
    exception_type: str = Field(description="Fully qualified exception class name")
    attempt: int = Field(
        description=(
            "Attempt number on which this error occurred. "
            "0 = rejected at pre-flight validation (never fetched). "
            "1+ = fetch attempt number."
        ),
        ge=0,
    )


class SymbolResult(BaseModel):
    """Result for a single symbol in a batch download.

    Invariants enforced by model_validator:
    - ``success=True``  → ``error is None``  and  ``bars`` may be non-empty
    - ``success=False`` → ``error is not None`` and ``bars`` is empty

    ``bars`` is always a list — never ``None``. Callers can iterate ``result.bars`` safely
    without a None-check regardless of success status.
    """

    symbol: str = Field(description="Canonical symbol in EXCHANGE:SYMBOL format")
    bars: list[OHLCVBar] = Field(
        default_factory=list,
        description="Fetched OHLCV bars, sorted chronologically (oldest first). Empty on failure.",
    )
    success: bool = Field(description="True if bars were fetched without error")
    error: ErrorInfo | None = Field(
        default=None,
        description="Structured error detail if success is False, else None",
    )
    attempts: int = Field(
        description=(
            "Number of fetch attempts made. "
            "0 = rejected at pre-flight (no fetch attempted). "
            "1+ = number of fetch attempts made."
        ),
        ge=0,
    )
    elapsed_seconds: float = Field(
        description="Wall-clock seconds spent across all attempts for this symbol",
        ge=0.0,
    )

    @model_validator(mode="after")
    def validate_success_invariants(self) -> SymbolResult:
        """Enforce consistency between success, error, and bars."""
        if self.success:
            if self.error is not None:
                raise ValueError("success=True but error is set — these are mutually exclusive")
        else:
            if self.error is None:
                raise ValueError("success=False requires error to be set")
            if self.bars:
                raise ValueError(
                    "success=False but bars is non-empty — bars must be empty on failure"
                )
        return self


class BatchDownloadSummary(BaseModel):
    """Aggregated result of a batch_download() call.

    ``results`` preserves the deduplicated input order — position i in ``results``
    corresponds to position i in the deduplicated symbol list.

    Counts (``total_count``, ``success_count``, ``failure_count``) are validated
    to be consistent with ``results`` to prevent mismatches that would make
    ``raise_if_failed()`` silently produce wrong behavior.
    """

    results: list[SymbolResult] = Field(
        description="One SymbolResult per deduplicated input symbol, in input order"
    )
    total_count: int = Field(description="Number of symbols after deduplication", ge=0)
    success_count: int = Field(description="Symbols fetched successfully", ge=0)
    failure_count: int = Field(description="Symbols that failed after all retries", ge=0)
    elapsed_seconds: float = Field(
        description="Total wall-clock seconds for the entire batch",
        ge=0.0,
    )
    interval: str = Field(description="Interval used for all fetches")

    @model_validator(mode="after")
    def validate_counts_consistent(self) -> BatchDownloadSummary:
        """Enforce that counts are consistent with results."""
        actual_total = len(self.results)
        actual_success = sum(1 for r in self.results if r.success)
        actual_failure = actual_total - actual_success

        if self.total_count != actual_total:
            raise ValueError(
                f"total_count={self.total_count} does not match len(results)={actual_total}"
            )
        if self.success_count != actual_success:
            raise ValueError(
                f"success_count={self.success_count} does not match actual successes={actual_success}"
            )
        if self.failure_count != actual_failure:
            raise ValueError(
                f"failure_count={self.failure_count} does not match actual failures={actual_failure}"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def failed_symbols(self) -> list[str]:
        """Canonical symbols that failed after all retry attempts."""
        return [r.symbol for r in self.results if not r.success]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def successful_symbols(self) -> list[str]:
        """Canonical symbols that were fetched successfully."""
        return [r.symbol for r in self.results if r.success]

    def raise_if_failed(self) -> None:
        """Raise BatchDownloadError if any symbol failed.

        Equivalent to having called batch_download() with strict=True, but
        callable after the fact — useful for pipelines that want to inspect
        the summary before deciding whether to treat failures as fatal.

        Raises:
            BatchDownloadError: If failure_count > 0.
        """
        if self.failure_count > 0:
            from tvkit.batch.exceptions import BatchDownloadError

            raise BatchDownloadError(
                f"{self.failure_count} of {self.total_count} symbols failed",
                summary=self,
            )


class BatchDownloadRequest(BaseModel):
    """Validated input parameters for batch_download().

    Exactly one fetch mode must be provided:
    - ``bars_count``: fetch the N most recent bars per symbol
    - ``start`` (with optional ``end``): fetch a date range per symbol

    ``start`` and ``end`` accept ISO 8601 strings or ``datetime`` objects; strings are
    parsed and naive datetimes normalized to UTC at construction time so downstream
    date arithmetic is always timezone-safe.

    ``auth_token`` is stored as SecretStr and never logged or repr'd in plain text.
    ``on_progress`` is excluded from model serialization (not JSON-safe).
    """

    symbols: list[str] = Field(
        min_length=1,
        description=(
            "List of TradingView symbols. Normalized and deduplicated before fetch. "
            "At least one symbol required."
        ),
    )
    interval: str = Field(
        default="1D",
        description="Timeframe interval. Valid values: '1', '5', '15', '30', '60', '1H', '4H', '1D', '1W', '1M'",
    )
    bars_count: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Number of historical bars to fetch per symbol (most recent N bars). "
            "Mutually exclusive with start/end."
        ),
    )
    start: datetime | None = Field(
        default=None,
        description=(
            "Range start. Accepts ISO 8601 string or datetime — normalized to UTC. "
            "Mutually exclusive with bars_count. end defaults to now if omitted."
        ),
    )
    end: datetime | None = Field(
        default=None,
        description=(
            "Range end. Accepts ISO 8601 string or datetime — normalized to UTC. "
            "Defaults to current UTC time if start is set but end is omitted."
        ),
    )
    concurrency: int = Field(
        default=5,
        ge=1,
        description="Maximum number of in-flight OHLCV connections at any moment.",
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Per-symbol retry limit (includes the initial attempt).",
    )
    base_backoff: float = Field(
        default=1.0,
        gt=0.0,
        description="Initial backoff in seconds. Doubles each attempt up to max_backoff.",
    )
    max_backoff: float = Field(
        default=30.0,
        gt=0.0,
        description="Maximum backoff ceiling in seconds.",
    )
    auth_token: SecretStr | None = Field(
        default=None,
        description="TradingView auth token. Stored as SecretStr — never logged. Equivalent to OHLCV(auth_token=...).",
    )
    browser: str | None = Field(
        default=None,
        description="Browser for cookie extraction. Accepted values: 'chrome', 'firefox'.",
    )
    on_progress: Callable[[SymbolResult, int, int], None] | None = Field(
        default=None,
        description=(
            "Optional sync callback invoked after each symbol resolves. "
            "Signature: (result: SymbolResult, completed: int, total: int) -> None. "
            "Called after both successes and failures. completed is 1-based. "
            "Async callables are rejected — this callback must be synchronous. "
            "Exceptions raised by the callback are logged and swallowed — a bad callback does not abort the batch."
        ),
        exclude=True,  # not JSON-serializable — excluded from model_dump()
    )
    validate_symbols_before_fetch: bool = Field(
        default=False,
        description=(
            "Pre-validate all symbols via TradingView HTTP API before fetching. "
            "Symbols confirmed invalid (HTTP 404) become SymbolResult(success=False, attempts=0) "
            "immediately — no WebSocket connection is opened for them. "
            "Validation failures due to transport or server errors fail open: the symbol "
            "proceeds to _fetch_one() unchanged. "
            "Not recommended for batches > 200 symbols — adds one HTTP call per symbol."
        ),
    )
    strict: bool = Field(
        default=False,
        description=(
            "If True, raise BatchDownloadError when any symbol fails. "
            "If False (default), failures are collected in BatchDownloadSummary."
        ),
    )

    model_config = {"arbitrary_types_allowed": True}  # required for Callable field

    @field_validator("start", "end", mode="before")
    @classmethod
    def parse_and_normalize_datetime(cls, value: str | datetime | None) -> datetime | None:
        """Parse ISO 8601 strings and normalize all datetimes to UTC-aware."""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid datetime string: {value!r}. "
                    "Expected ISO 8601 format, e.g. '2024-01-01' or '2024-01-01T00:00:00Z'."
                ) from exc
        return _to_utc_aware(value)

    @field_validator("interval")
    @classmethod
    def validate_interval_value(cls, value: str) -> str:
        """Validate against known TradingView interval formats."""
        validate_interval(value)
        return value

    @field_validator("browser")
    @classmethod
    def validate_browser_value(cls, value: str | None) -> str | None:
        """Validate browser is one of the supported values."""
        if value is not None and value not in _VALID_BROWSERS:
            raise ValueError(
                f"Invalid browser: {value!r}. Must be one of: {sorted(_VALID_BROWSERS)}"
            )
        return value

    @field_validator("on_progress", mode="before")
    @classmethod
    def reject_async_callback(
        cls, value: Callable[[SymbolResult, int, int], None] | None
    ) -> Callable[[SymbolResult, int, int], None] | None:
        """Reject coroutine functions — on_progress must be synchronous."""
        if value is not None and inspect.iscoroutinefunction(value):
            raise ValueError(
                "on_progress must be a synchronous callable. "
                "Async callables are not supported — the callback is invoked without await."
            )
        return value

    @model_validator(mode="after")
    def validate_fetch_mode(self) -> BatchDownloadRequest:
        """Enforce mutual exclusivity between bars_count and start/end, and range order."""
        has_bars = self.bars_count is not None
        has_start = self.start is not None
        if has_bars and has_start:
            raise ValueError(
                "Provide bars_count or start/end, not both. "
                "bars_count fetches the N most recent bars; start/end fetches a date range."
            )
        if not has_bars and not has_start:
            raise ValueError(
                "Either bars_count or start must be provided. "
                "Use bars_count for the N most recent bars, or start (with optional end) for a date range."
            )
        if has_start and self.end is not None:
            # Both are UTC-aware at this point (normalized in field_validator).
            # has_start guarantees self.start is not None; checked explicitly for type safety.
            if self.start is None:  # pragma: no cover
                raise ValueError("Internal error: has_start is True but self.start is None")
            if self.end <= self.start:
                raise ValueError(
                    f"end ({self.end.isoformat()}) must be after start ({self.start.isoformat()})."
                )
        return self
