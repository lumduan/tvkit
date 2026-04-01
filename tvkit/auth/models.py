"""TradingView account data models for tvkit.auth."""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Literal

__all__ = ["TradingViewAccount"]


@dataclass
class TradingViewAccount:
    """
    Detected account capabilities after authentication and profile fetch.

    ``max_bars`` starts as a plan-based estimate immediately after cookie
    extraction and is updated in-place by the background capability probe
    when it completes. All updates to ``max_bars`` should be guarded by
    the ``_lock`` field to prevent race conditions when multiple coroutines
    use the session concurrently.

    ``SegmentedFetchService`` snapshots ``max_bars`` once at the start of
    each fetch to ensure stable segment boundaries throughout a single request.

    Args:
        user_id: TradingView numeric user ID.
        username: TradingView display username.
        plan: Raw ``pro_plan`` string from the TradingView user profile
            (e.g. ``"pro_premium"``, ``"ultimate"``). Preserved verbatim.
            Unknown values default to ``max_bars=5000`` with a WARNING logged.
        tier: Normalised user-facing tier string derived from ``plan``.
            One of ``"free"``, ``"pro"``, ``"premium"``, ``"ultimate"``.
        is_pro: ``True`` if the account has any paid subscription.
        is_broker: ``True`` if the account has broker capabilities.
        max_bars: Current maximum bars per WebSocket request. Starts as the
            plan-based estimate; updated by the background probe when confirmed.
            Guarded by ``_lock`` for concurrent access safety.
        estimated_max_bars: Immutable plan-based estimate captured at login.
            Never mutated after construction — used for debugging and
            observability only (compare estimate vs confirmed value).
        probe_confirmed: ``True`` once the background probe has confirmed
            the actual server-enforced ``max_bars`` limit.
        max_bars_source: Where the current ``max_bars`` value came from.
            ``"estimate"`` immediately after cookie extraction;
            updated to ``"probe"`` when the background probe confirms the
            actual limit. Use this field (not ``probe_confirmed``) to
            determine the source of the current ``max_bars`` value.
        probe_status: Current probe lifecycle state.
            ``"pending"`` — probe not yet started or in progress.
            ``"success"`` — probe confirmed ``max_bars``.
            ``"throttled"`` — probe was rate-limited; estimate kept.
            ``"failed"`` — all symbol+bars combinations exhausted; estimate kept.
    """

    user_id: int
    username: str
    plan: str
    tier: str
    is_pro: bool
    is_broker: bool
    max_bars: int
    estimated_max_bars: int
    probe_confirmed: bool = False
    max_bars_source: Literal["estimate", "probe"] = "estimate"
    probe_status: Literal["pending", "success", "throttled", "failed"] = "pending"
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)

    def __repr__(self) -> str:
        """Safe repr — masks username beyond first 3 chars to prevent PII in logs."""
        masked = (self.username[:3] + "***") if self.username else "***"
        return (
            f"TradingViewAccount("
            f"user_id={self.user_id}, "
            f"username={masked!r}, "
            f"plan={self.plan!r}, "
            f"tier={self.tier!r}, "
            f"max_bars={self.max_bars}, "
            f"max_bars_source={self.max_bars_source!r}, "
            f"probe_confirmed={self.probe_confirmed})"
        )

    @classmethod
    def from_profile(
        cls,
        profile: dict[str, Any],
        max_bars: int,
        tier: str,
    ) -> "TradingViewAccount":
        """
        Construct a ``TradingViewAccount`` from a parsed TradingView user profile.

        Args:
            profile: Parsed ``user`` object from the TradingView homepage bootstrap.
                Must contain ``id``, ``username``, ``pro_plan``, ``is_pro``,
                ``is_broker`` fields.
            max_bars: Plan-based ``max_bars`` estimate from ``CapabilityDetector``.
            tier: Normalised tier string from ``CapabilityDetector``.

        Returns:
            A fully populated ``TradingViewAccount`` with ``max_bars_source``
            set to ``"estimate"`` and ``probe_status`` set to ``"pending"``.
        """
        return cls(
            user_id=int(profile["id"]),
            username=str(profile["username"]),
            plan=str(profile.get("pro_plan", "")),
            tier=tier,
            is_pro=bool(profile.get("is_pro", False)),
            is_broker=bool(profile.get("is_broker", False)),
            max_bars=max_bars,
            estimated_max_bars=max_bars,
            probe_confirmed=False,
            max_bars_source="estimate",
            probe_status="pending",
        )
