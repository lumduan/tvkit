"""Exception types for the tvkit.batch package."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tvkit.batch.models import BatchDownloadSummary

__all__ = ["BatchDownloadError"]


class BatchDownloadError(Exception):
    """Raised by batch_download() when strict=True and one or more symbols fail.

    Also raised by BatchDownloadSummary.raise_if_failed() after the fact.
    The summary is always attached so callers can inspect partial results even
    when this exception is raised.

    Attributes:
        summary: The full BatchDownloadSummary, including successful results.

    Example:
        >>> try:
        ...     summary = await batch_download(request)
        ... except BatchDownloadError as exc:
        ...     print(f"Failed symbols: {exc.failed_symbols}")
        ...     for result in exc.summary.results:
        ...         if result.success:
        ...             process(result)
    """

    def __init__(self, message: str, summary: BatchDownloadSummary) -> None:
        super().__init__(message)
        self.summary: BatchDownloadSummary = summary

    @property
    def failed_symbols(self) -> list[str]:
        """Canonical symbols that failed after all retry attempts."""
        return self.summary.failed_symbols
