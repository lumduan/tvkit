"""Segmented fetch orchestrator for large historical OHLCV date ranges."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from tvkit.api.chart.exceptions import NoHistoricalDataError, SegmentedFetchError
from tvkit.api.chart.models.adjustment import Adjustment
from tvkit.api.chart.models.ohlcv import OHLCVBar
from tvkit.api.chart.utils import (
    MAX_BARS_REQUEST,
    TimeSegment,
    interval_to_seconds,
    segment_time_range,
)

if TYPE_CHECKING:
    from tvkit.api.chart.ohlcv import OHLCV

logger: logging.Logger = logging.getLogger(__name__)


class SegmentedFetchService:
    """
    Orchestrates segmented historical OHLCV fetching for large date ranges.

    Splits a date range into segments sized for at most ``max_bars_per_segment``
    bars each, fetches segments sequentially using ``OHLCV._fetch_single_range()``
    (the private internal method — **NOT** the public ``get_historical_ohlcv()``,
    which would cause infinite recursion), then merges, deduplicates by timestamp,
    and sorts results chronologically.

    This service is an internal implementation detail of ``OHLCV.get_historical_ohlcv()``.
    It is not part of the public API and must not be instantiated directly by callers.

    Args:
        client:               Reference to the ``OHLCV`` client instance.
        max_bars_per_segment: Maximum bars per segment. Defaults to ``MAX_BARS_REQUEST``
                              (5000). Lowering this value increases the number of
                              segments and reduces per-segment memory usage.
    """

    def __init__(
        self,
        client: OHLCV,
        max_bars_per_segment: int = MAX_BARS_REQUEST,
    ) -> None:
        self._client = client
        self._max_bars_per_segment: int = max_bars_per_segment

    def _resolve_max_bars(self) -> int:
        """
        Return the effective max_bars for this fetch.

        If the OHLCV client has an authenticated AuthManager with account capability
        data, use ``auth_manager.account.max_bars`` (probe-confirmed or plan estimate).
        Otherwise fall back to the constructor-supplied ``_max_bars_per_segment``
        (default: ``MAX_BARS_REQUEST`` = 5000 for anonymous sessions).

        ``getattr`` is used for safe access because ``SegmentedFetchService`` may be
        used in tests where ``_auth_manager`` was never set on the mock client.

        Returns:
            Effective maximum bars per segment for this fetch.
        """
        auth_manager = getattr(self._client, "_auth_manager", None)
        if auth_manager is not None and auth_manager.account is not None:
            return auth_manager.account.max_bars
        return self._max_bars_per_segment

    async def fetch_all(
        self,
        exchange_symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
        *,
        adjustment: Adjustment = Adjustment.SPLITS,
    ) -> list[OHLCVBar]:
        """
        Fetch all OHLCV bars for the given range by splitting into segments.

        Accepts UTC-aware ``datetime`` objects only. Normalization from ``str``
        or naive datetimes must be performed by the caller
        (``OHLCV.get_historical_ohlcv()``) via ``_to_utc_datetime()`` before
        invoking this method. This enforces a clear layer boundary: ``OHLCV``
        owns all user-input parsing; this service operates exclusively on
        normalized datetime values.

        Args:
            exchange_symbol: TradingView symbol in ``EXCHANGE:SYMBOL`` format
                             (e.g. ``"NASDAQ:AAPL"``). Must already be validated
                             and normalized by the caller.
            interval:        TradingView interval string (e.g. ``"1"``, ``"1H"``,
                             ``"1D"``). Must be supported by ``interval_to_seconds()``
                             — monthly and weekly intervals raise ``ValueError``
                             before any fetch is attempted.
            start:           Inclusive start of the date range (UTC-aware datetime).
            end:             Inclusive end of the date range (UTC-aware datetime).
            adjustment:      Price adjustment mode forwarded to each
                             ``_fetch_single_range()`` call. Defaults to
                             ``Adjustment.SPLITS`` (backwards-compatible). Pass
                             ``Adjustment.DIVIDENDS`` for dividend-adjusted prices.

        Returns:
            Deduplicated, chronologically sorted list of ``OHLCVBar`` objects.
            Returns ``[]`` if no bars are available for the entire requested range
            (e.g. the range covers only weekends or market holidays). This is not
            an error condition.

        Raises:
            ValueError:         If ``interval`` is monthly/weekly (not supported by
                                the segmentation engine) or if ``start > end``.
            RangeTooLargeError: If the computed segment count exceeds ``MAX_SEGMENTS``
                                (2000). Raised by ``segment_time_range()`` before any
                                fetch begins.
            SegmentedFetchError: If any individual segment fetch fails with an
                                 exception other than ``NoHistoricalDataError``.
                                 Contains full segment context: index, start, end,
                                 total segments, and the original cause.

        Example:
            >>> from datetime import datetime, UTC
            >>> async with OHLCV() as client:
            ...     service = SegmentedFetchService(client)
            ...     bars = await service.fetch_all(
            ...         "NASDAQ:AAPL", "1", datetime(2023, 1, 1, tzinfo=UTC),
            ...         datetime(2023, 12, 31, tzinfo=UTC),
            ...     )
            ...     print(len(bars))
        """
        # Snapshot max_bars at fetch start — stable for the entire fetch even if
        # the background capability probe updates auth_manager.account.max_bars mid-flight.
        max_bars: int = self._resolve_max_bars()
        interval_secs: int = interval_to_seconds(interval)
        segments: list[TimeSegment] = segment_time_range(start, end, interval_secs, max_bars)

        total: int = len(segments)
        auth_manager = getattr(self._client, "_auth_manager", None)
        account = auth_manager.account if auth_manager is not None else None
        logger.info(
            "Starting segmented fetch.",
            extra={
                "symbol": exchange_symbol,
                "interval": interval,
                "segments": total,
                "max_bars_per_segment": max_bars,
                "max_bars_source": account.max_bars_source if account is not None else "default",
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
        )

        all_bars: list[OHLCVBar] = []

        # Log at INFO every ~10% of segments, plus the first and last.
        # Avoids flooding production logs for large fetches (350+ segments).
        log_interval: int = max(1, total // 10)

        for i, segment in enumerate(segments, start=1):
            progress_pct: float = round(i / total * 100, 1)
            is_milestone: bool = i % log_interval == 0 or i == 1 or i == total
            fetch_kwargs = {
                "segment": i,
                "total_segments": total,
                "progress_pct": progress_pct,
                "segment_start": segment.start.isoformat(),
                "segment_end": segment.end.isoformat(),
            }

            if is_milestone:
                logger.info("Fetching segment.", extra=fetch_kwargs)
            else:
                logger.debug("Fetching segment.", extra=fetch_kwargs)

            try:
                # IMPORTANT: Call _fetch_single_range(), NOT get_historical_ohlcv().
                # The public method contains the segmentation dispatch check — calling
                # it here would cause infinite recursion for any segment whose
                # estimated bar count still exceeds MAX_BARS_REQUEST.
                #
                # _fetch_single_range() is extracted from get_historical_ohlcv() in
                # Phase 4. The type: ignore suppresses the "no attribute" error until
                # Phase 4 adds the method to OHLCV. Remove the ignore after Phase 4.
                bars: list[OHLCVBar] = await self._client._fetch_single_range(
                    exchange_symbol,
                    interval,
                    start=segment.start,
                    end=segment.end,
                    adjustment=adjustment,
                )
            except NoHistoricalDataError:
                # Expected for segments covering weekends, holidays, or illiquid
                # periods. Treat as an empty result — not a failure.
                logger.debug(
                    "Segment returned no bars (market closed or no data in range).",
                    extra={"segment": i, "segment_start": segment.start.isoformat()},
                )
                bars = []
            except Exception as exc:
                logger.error(
                    "Segment fetch failed.",
                    extra={
                        "segment": i,
                        "total_segments": total,
                        "error": str(exc),
                    },
                )
                raise SegmentedFetchError(
                    segment_index=i,
                    segment_start=segment.start,
                    segment_end=segment.end,
                    total_segments=total,
                    cause=exc,
                ) from exc

            all_bars.extend(bars)
            complete_kwargs = {
                "segment": i,
                "total_segments": total,
                "progress_pct": progress_pct,
                "segment_bars": len(bars),
                "total_bars_so_far": len(all_bars),
            }
            if is_milestone:
                logger.info("Segment complete.", extra=complete_kwargs)
            else:
                logger.debug("Segment complete.", extra=complete_kwargs)

        result: list[OHLCVBar] = self._deduplicate_and_sort(all_bars)

        logger.info(
            "Segmented fetch complete.",
            extra={
                "symbol": exchange_symbol,
                "total_bars": len(result),
                "segments_fetched": total,
            },
        )
        return result

    @staticmethod
    def _deduplicate_and_sort(bars: list[OHLCVBar]) -> list[OHLCVBar]:
        """
        Deduplicate bars by timestamp (first occurrence wins) and sort ascending.

        ``segment_time_range()`` produces non-overlapping segment boundaries, so
        deduplication is primarily a safety net for edge cases where TradingView
        bleeds a boundary bar into two consecutive segments. First-occurrence
        semantics give precedence to the earlier segment, which is the authoritative
        source for any bar that appears at a segment boundary.

        Args:
            bars: Accumulated OHLCV bars from all segments, in segment order.

        Returns:
            Deduplicated list sorted ascending by ``OHLCVBar.timestamp``.
            Returns ``[]`` if ``bars`` is empty.

        Note:
            Time complexity: O(n) for deduplication (hash set) + O(n log n) for sort.
            For v0.5.0, in-memory accumulation is acceptable. Streaming via async
            generator is noted as a future enhancement in the project roadmap.
        """
        seen: set[float] = set()
        unique: list[OHLCVBar] = []
        for bar in bars:
            if bar.timestamp not in seen:
                seen.add(bar.timestamp)
                unique.append(bar)
        unique.sort(key=lambda bar: bar.timestamp)
        return unique
