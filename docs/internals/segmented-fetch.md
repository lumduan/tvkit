# Segmented Fetch Internals

**Available since:** v0.5.0
**Class:** `tvkit.api.chart.services.segmented_fetch_service.SegmentedFetchService`

This document describes the internal implementation of automatic segmented historical OHLCV fetching. It is intended for contributors. Callers should use `get_historical_ohlcv()` and refer to the [OHLCV reference](../reference/chart/ohlcv.md).

---

## Overview

When a caller requests a date range that would produce more than `MAX_BARS_REQUEST` (5,000) bars in a single request, `get_historical_ohlcv()` delegates to `SegmentedFetchService.fetch_all()`. This service splits the range into segments, fetches each one sequentially via `OHLCV._fetch_single_range()`, then merges, deduplicates, and sorts the results before returning a single `list[OHLCVBar]`.

---

## Dispatch Decision

The dispatch is decided in `OHLCV.get_historical_ohlcv()` by `_needs_segmentation(start, end, interval)`:

```text
_needs_segmentation(start, end, interval):
    if interval is monthly or weekly → return False  (single request, always)
    interval_secs = interval_to_seconds(interval)
    estimated_bars = (end - start).total_seconds() / interval_secs
    return estimated_bars > MAX_BARS_REQUEST
```

If `True`, `get_historical_ohlcv()` constructs a `SegmentedFetchService` and calls `fetch_all()`. Monthly and weekly intervals are always excluded because `interval_to_seconds()` raises `ValueError` for them — segmentation cannot size those windows with a fixed-second formula.

---

## Segment Sizing Formula

Given:
- `interval_seconds` — bar duration in seconds
- `max_bars` — maximum bars per segment (default: `MAX_BARS_REQUEST = 5000`)

```text
segment_delta = (max_bars - 1) * interval_seconds
```

`segment_delta` is the time span of one full segment. The `- 1` accounts for the fact that a segment with N bars has N - 1 gaps between them, so the final bar falls at `start + segment_delta`, not `start + max_bars * interval_seconds`.

---

## Segment Boundary Algebra

`segment_time_range()` uses a cursor loop:

```text
cursor = start
while cursor <= end:
    seg_end = min(cursor + segment_delta, end)
    emit TimeSegment(start=cursor, end=seg_end)
    cursor = seg_end + interval_seconds   ← advance past last bar of segment
```

Key invariants:

| Property | Guarantee |
| -------- | --------- |
| Non-overlapping | `segs[i].end < segs[i+1].start` for all i |
| No gap | `segs[i+1].start == segs[i].end + interval_seconds` |
| Full coverage | `segs[0].start == start` and `segs[-1].end == end` |
| Last clamped | The last segment's end is always exactly `end`, never beyond |

---

## Recursion Guard

`SegmentedFetchService.fetch_all()` calls `self._client._fetch_single_range()`, **not** `self._client.get_historical_ohlcv()`.

This is a hard requirement. `get_historical_ohlcv()` calls `_needs_segmentation()` before dispatching — if it were called from inside `fetch_all()`, any segment whose bar count still exceeded `MAX_BARS_REQUEST` (which should not happen given correct sizing, but could occur due to rounding) would recurse infinitely.

`_fetch_single_range()` is the extracted raw fetch primitive: it issues one WebSocket request for a given `(symbol, interval, start, end)` tuple and returns `list[OHLCVBar]`.

---

## Empty Segment Handling

`_fetch_single_range()` raises `NoHistoricalDataError` when TradingView returns no bars for a segment (weekends, public holidays, illiquid periods, or dates outside the accessible history window).

`fetch_all()` catches this exception and treats it as an empty result (`bars = []`). It is **never** wrapped in `SegmentedFetchError`. This keeps the return contract simple: empty segments are silently skipped.

Any other exception from `_fetch_single_range()` is wrapped in `SegmentedFetchError` and re-raised immediately, aborting the fetch. `SegmentedFetchError` carries:

- `segment_index` — 1-based index of the failed segment
- `segment_start` / `segment_end` — the failing segment's time window
- `total_segments` — total segments planned
- `cause` — the original exception

---

## Merge and Deduplication Semantics

After all segments are fetched, `_deduplicate_and_sort(bars)` is called:

```text
_deduplicate_and_sort(bars):
    seen = set()
    unique = []
    for bar in bars:           ← iterate in segment order (earliest first)
        if bar.timestamp not in seen:
            seen.add(bar.timestamp)
            unique.append(bar)
    unique.sort(key=lambda b: b.timestamp)
    return unique
```

**First-occurrence-wins** semantics: if TradingView bleeds a boundary bar into both the end of one segment and the start of the next, the earlier segment's copy is kept. This is the authoritative source because `_fetch_single_range()` returns the actual bar data for the requested window — not an interpolation.

Time complexity: O(n) deduplication (hash set) + O(n log n) sort.

---

## Progress Logging

`fetch_all()` logs at `INFO` for milestone segments and `DEBUG` for all others:

```text
log_interval = max(1, total // 10)   ← log every ~10% of segments
is_milestone = (i % log_interval == 0) or (i == 1) or (i == total)
```

For a 350-segment fetch, this produces ~36 INFO lines (first, last, and every 35th) rather than 350. For small fetches (< 10 segments), every segment is a milestone.

### Possible Future Enhancement (Heuristic Warning)

A heuristic warning could be emitted when the segment count and interval suggest the request is likely to fall outside the accessible TradingView history window for free-tier accounts (e.g., `total_segments * interval_seconds > 3.5 * 86400` for 1-minute bars). This advisory log would help users diagnose unexpectedly short result sets without requiring access to TradingView account tier information. This enhancement is deferred — it is not implemented in v0.5.0.

---

## Sequence Diagram

```text
Caller
  │
  ▼
get_historical_ohlcv(symbol, interval, start, end)
  │
  ├─ _needs_segmentation(start, end, interval)
  │     ├─ monthly/weekly → False → single _fetch_single_range() call
  │     └─ estimated_bars > MAX_BARS_REQUEST → True
  │
  ├─ SegmentedFetchService(client=self)
  │
  └─ fetch_all(symbol, interval, start, end)
        │
        ├─ interval_to_seconds(interval)
        ├─ segment_time_range(start, end, interval_secs, max_bars)
        │     └─ raises RangeTooLargeError if count > MAX_SEGMENTS
        │
        ├─ for each segment [1..N]:
        │     ├─ _fetch_single_range(symbol, interval, seg.start, seg.end)
        │     │     ├─ NoHistoricalDataError → bars = []  (skip)
        │     │     └─ Exception → SegmentedFetchError    (abort)
        │     └─ all_bars.extend(bars)
        │
        └─ _deduplicate_and_sort(all_bars)
              └─ returns list[OHLCVBar]
```

---

## See Also

- [Historical Data Guide](../guides/historical-data.md) — user-facing segmentation explanation
- [OHLCV Client Reference](../reference/chart/ohlcv.md) — `get_historical_ohlcv()` signature
- [Chart Utilities Reference](../reference/chart/utils.md) — `segment_time_range()`, `TimeSegment`, `interval_to_seconds()`
- [Limitations](../limitations.md) — TradingView historical depth and other constraints
