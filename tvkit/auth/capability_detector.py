"""TradingView account capability detection for tvkit.auth."""

import logging
from typing import Any

__all__ = ["CapabilityDetector", "PLAN_TO_BARS", "PLAN_TO_TIER"]

logger: logging.Logger = logging.getLogger(__name__)

# Known plan slug → max bars mapping (plan-based estimates; confirmed by probe).
PLAN_TO_BARS: dict[str, int] = {
    "": 5_000,
    "pro": 10_000,
    "pro_plus": 10_000,
    "pro_premium": 20_000,
    "ultimate": 40_000,
}

# Known plan slug → normalised tier string.
PLAN_TO_TIER: dict[str, str] = {
    "": "free",
    "pro": "pro",
    "pro_plus": "pro",
    "pro_premium": "premium",
    "ultimate": "ultimate",
}


class CapabilityDetector:
    """
    Estimates account capability limits from a TradingView user profile.

    Uses the ``pro_plan`` field with a badge fallback for free accounts, an
    exact lookup in ``PLAN_TO_BARS``, and a substring heuristic for unknown
    future plan slugs introduced by TradingView.
    """

    @staticmethod
    def estimate_from_plan(
        pro_plan: str,
        badges: list[Any],
    ) -> tuple[int, str]:
        """
        Estimate ``(max_bars, tier)`` from a TradingView account's plan information.

        Resolution order:

        1. Normalize ``pro_plan`` to lowercase.
        2. If empty, scan ``badges`` for a ``"pro:<plan>"`` prefix (string or dict form).
        3. Exact lookup in ``PLAN_TO_BARS``.
        4. Substring heuristic for unknown slugs (``"ultimate"`` > ``"premium"`` > ``"pro"``).
        5. Fallback: free tier (5,000 bars) + WARNING logged.

        Args:
            pro_plan: Raw ``pro_plan`` value from the TradingView user profile.
            badges: ``badges`` list from the TradingView user profile. Each item
                may be a plain string (``"pro:pro_premium"``) or a dict
                (``{"name": "pro:pro_premium", ...}``).

        Returns:
            A ``(max_bars, tier)`` tuple where ``tier`` is one of
            ``"free"``, ``"pro"``, ``"premium"``, ``"ultimate"``.
        """
        plan = CapabilityDetector._resolve_plan(pro_plan, badges)
        return CapabilityDetector._plan_to_capacity(plan)

    @staticmethod
    def _resolve_plan(pro_plan: str, badges: list[Any]) -> str:
        """
        Resolve the effective plan slug from ``pro_plan`` and badge fallback.

        Normalizes the plan string to lowercase before any comparison. If
        ``pro_plan`` is empty, scans the ``badges`` list for a ``"pro:<plan>"``
        prefixed entry.

        Args:
            pro_plan: Raw ``pro_plan`` from the user profile.
            badges: ``badges`` list from the user profile.

        Returns:
            The resolved (and lowercased) plan slug, or ``""`` if none found.
        """
        plan = (pro_plan or "").lower()

        if not plan:
            for badge in badges:
                name: str | None
                if isinstance(badge, str):
                    name = badge
                elif isinstance(badge, dict):
                    name = badge.get("name")
                else:
                    name = None

                if name and name.startswith("pro:"):
                    plan = name.split(":", 1)[1].lower()
                    break

        return plan

    @staticmethod
    def _plan_to_capacity(plan: str) -> tuple[int, str]:
        """
        Map a resolved plan slug to ``(max_bars, tier)``.

        Applies exact lookup first, then a substring heuristic for unknown slugs,
        and finally falls back to the free tier with a WARNING.

        Args:
            plan: Lowercased, resolved plan slug.

        Returns:
            ``(max_bars, tier)`` tuple.
        """
        if plan in PLAN_TO_BARS:
            return PLAN_TO_BARS[plan], PLAN_TO_TIER[plan]

        # Heuristic for unknown future plan slugs (e.g. "pro_essential", "pro_standard").
        if "ultimate" in plan:
            logger.warning(
                "Unknown pro_plan '%s' matched heuristic 'ultimate' — using 40,000 bars.", plan
            )
            return 40_000, "ultimate"
        if "premium" in plan:
            logger.warning(
                "Unknown pro_plan '%s' matched heuristic 'premium' — using 20,000 bars.", plan
            )
            return 20_000, "premium"
        if "pro" in plan:
            logger.warning(
                "Unknown pro_plan '%s' matched heuristic 'pro' — using 10,000 bars.", plan
            )
            return 10_000, "pro"

        logger.warning(
            "Unrecognised pro_plan '%s' — defaulting to free tier (5,000 bars). "
            "This may cause reduced historical data depth for paying accounts.",
            plan,
        )
        return 5_000, "free"
