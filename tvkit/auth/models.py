"""TradingView account data models for tvkit.auth."""

from dataclasses import dataclass
from typing import Any

__all__ = ["TradingViewAccount"]


@dataclass
class TradingViewAccount:
    """
    Represents a TradingView user account with plan and capability information.

    Populated during the Stage 2 login flow by ``AuthManager``. The ``max_bars``
    field starts as the plan-based estimate and is updated in-place by the
    background capability probe (Phase 5) when confirmed.

    Attributes:
        user_id: TradingView numeric user identifier.
        username: TradingView display username.
        plan: Raw ``pro_plan`` string from the TradingView user profile
            (e.g. ``"pro_premium"``, ``"ultimate"``). Preserved verbatim.
        tier: Normalised user-facing tier string. One of:
            ``"free"``, ``"pro"``, ``"premium"``, ``"ultimate"``.
        is_pro: ``True`` if the account has any paid plan.
        is_broker: ``True`` if the account has broker capabilities.
        max_bars: Current maximum bars estimate. Updated by the background probe
            when confirmed. Read by ``SegmentedFetchService`` at fetch start.
        estimated_max_bars: Immutable plan-based estimate captured at login.
            Never mutated after construction — used for debugging comparison.
        probe_confirmed: ``True`` once the background probe has confirmed the
            actual server-enforced ``max_bars`` limit.
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
            A fully populated ``TradingViewAccount`` instance.
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
        )
