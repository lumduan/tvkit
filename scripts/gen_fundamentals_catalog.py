#!/usr/bin/env python3
"""Generate ``tvkit/api/fundamentals/catalog.py`` from a saved ``fundamentals_config_v2``
snapshot (TradingView's field dictionary).

The catalog drives statement field selection and row ordering so the client never has to
guess field ids by name-substring (which would confuse near-duplicates such as
``minority_interest`` [balance sheet] vs ``minority_interest_exp`` [income statement], or
``non_oper_income`` vs ``total_non_oper_income``).

Usage:
    uv run python scripts/gen_fundamentals_catalog.py \
        tests/fixtures/fundamentals/config_v2.json \
        tvkit/api/fundamentals/catalog.py

The snapshot is captured once (anonymous ``GET
https://www.tradingview.com/financial/fundamentals_config_v2/``) and kept as a test fixture;
re-run this script to refresh the catalog when TradingView adds statement lines.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Snapshot ``category`` value → our StatementType slug.
CATEGORY_TO_STATEMENT: dict[str, str] = {
    "Income statements": "income",
    "Balance sheet": "balance",
    "Cash flow": "cash_flow",
    "Statistics": "statistics",
}

# Period suffixes we retain (statement periods). Longest first for correct stripping.
_PERIOD_SUFFIXES: tuple[str, ...] = ("ttm", "fy", "fq", "fh")


def _strip_period(field_id: str) -> str | None:
    """Return the period-stripped base of a field id, or None if it has no known suffix."""
    for suf in _PERIOD_SUFFIXES:
        if field_id.endswith("_" + suf):
            return field_id[: -(len(suf) + 1)]
    return None


def build(snapshot: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the catalog structure from the raw config entries.

    Only **top-level** statement rows (``parent is None``) are catalogued — these are the
    lines the UI table shows by default and that the recon oracle verified. Sub-line children
    (expandable breakdowns) are intentionally excluded from v1.

    Ordinal + parent are read from the ``FY`` entry per (base, fund_view_mode); ``FQ`` is a
    fallback for the rare base with no annual variant.

    Returns:
      - ``request``: {statement: sorted[unique base ids]} — union across templates to request
        (the server omits lines the issuer does not report).
      - ``order``: {statement: {fund_view_mode: [base, ...] in ordinal order}} — display order.
      - ``labels``: {base: display name} — human labels for rows.
    """
    # (base, fvm) → (period_rank, ordinal, name); lower period_rank wins (FY over FQ).
    layout: dict[tuple[str, str, str], tuple[int, int, str]] = {}
    request: dict[str, set[str]] = defaultdict(set)
    _period_rank = {"FY": 0, "FQ": 1, "FH": 2, "TTM": 3}

    for entry in snapshot:
        statement = CATEGORY_TO_STATEMENT.get(entry.get("category") or "")
        if statement is None:
            continue
        if not entry.get("financialVisible") or entry.get("hidden"):
            continue
        if entry.get("parent") is not None:  # top-level rows only
            continue
        base = _strip_period(str(entry.get("id", "")))
        if base is None:
            continue
        ordinal = entry.get("ordinal")
        if not isinstance(ordinal, int):
            continue
        rank = _period_rank.get(entry.get("period") or "", 9)
        fvm = entry.get("fundViewMode") or "other"
        key = (statement, fvm, base)
        prev = layout.get(key)
        if prev is None or rank < prev[0]:
            layout[key] = (rank, ordinal, str(entry.get("name") or base))
        request[statement].add(base)

    # Labels: prefer the FY entry, and the industrial template when templates disagree
    # (e.g. oper_income = "Operating income" industrial vs "Net operating profit" banking).
    _fvm_priority = {"industrial": 0, "insurance": 1, "other": 2, "banking": 3}
    labels: dict[str, str] = {}
    _label_rank: dict[str, tuple[int, int]] = {}
    for (_statement, fvm, base), (rank, _ordinal, name) in layout.items():
        combined = (rank, _fvm_priority.get(fvm, 9))
        if base not in labels or combined < _label_rank.get(base, (9, 9)):
            labels[base] = name
            _label_rank[base] = combined

    order: dict[str, dict[str, list[str]]] = defaultdict(dict)
    grouped: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    for (statement, fvm, base), (_, ordinal, _name) in layout.items():
        grouped[(statement, fvm)].append((ordinal, base))
    for (statement, fvm), items in grouped.items():
        order[statement][fvm] = [b for _, b in sorted(items, key=lambda t: t[0])]

    return {
        "request": {k: sorted(v) for k, v in request.items()},
        "order": {k: dict(v) for k, v in order.items()},
        "labels": labels,
    }


_HEADER = '''"""TradingView fundamentals field catalog — GENERATED, do not edit by hand.

Regenerate with::

    uv run python scripts/gen_fundamentals_catalog.py \\
        tests/fixtures/fundamentals/config_v2.json tvkit/api/fundamentals/catalog.py

Derived from TradingView's ``fundamentals_config_v2`` dictionary. Maps each statement to the
set of period-stripped field-id bases to request and the per-template display order. See
``docs/concepts/financial-statements.md``.
"""

from __future__ import annotations

# Statement period suffixes appended to a base id (history arrays use the ``_h`` variant).
PERIOD_SUFFIX: dict[str, str] = {
    "FY": "fy",
    "FQ": "fq",
    "FH": "fh",
    "TTM": "ttm",
}

# Structural fields (NOT in the config dictionary) that align history arrays to periods and
# carry currency/template metadata. Requested with every statement snapshot.
PERIOD_FIELDS: dict[str, list[str]] = {
    "FY": ["fiscal_period_fy_h", "fiscal_period_end_fy_h"],
    "FQ": ["fiscal_period_fq_h", "fiscal_period_end_fq_h"],
    "FH": ["fiscal_period_fh_h", "fiscal_period_end_fh_h"],
    "TTM": ["fiscal_period_fq_h", "fiscal_period_end_fq_h"],
}
META_FIELDS: list[str] = ["fundamental_currency_code", "currency_code", "report_type"]

# Revenue segments (P0) — structural quote fields, not in the config dictionary.
SEGMENT_FIELDS: list[str] = ["revenue_seg_by_business_h", "revenue_seg_by_region_h"]

# Dividend events history + summary (aligned to each other, not to fiscal periods).
DIVIDEND_EVENT_FIELDS: list[str] = [
    "dividend_amount_h",
    "dividend_ex_date_h",
    "dividend_payment_date_h",
    "dividend_record_date_h",
    "dividend_type_h",
]
DIVIDEND_SUMMARY_FIELDS: list[str] = [
    "dividend_amount_recent",
    "dividend_ex_date_recent",
    "dividend_payment_date_recent",
    "dividend_yield_recent",
    "dividends_paid",
    "dividend_payout_ratio_ttm",
    "dividend_payout_ratio_fy_h",
    "dividends_availability",
]

# Earnings — reported vs estimate + surprise, keyed by earnings/estimates period arrays.
EARNINGS_FIELDS: dict[str, list[str]] = {
    "FQ": [
        "earnings_per_share_fq_h",
        "earnings_per_share_diluted_fq_h",
        "earnings_estimate_fq_h",
        "earnings_per_share_forecast_fq_h",
        "revenues_fq_h",
        "revenues_estimate_fq_h",
        "earnings_fiscal_period_fq_h",
        "earnings_release_date_fq_h",
    ],
    "FY": [
        "earnings_per_share_fy_h",
        "earnings_per_share_diluted_fy_h",
        "earnings_estimate_fy_h",
        "earnings_per_share_forecast_fy_h",
        "revenues_fy_h",
        "revenues_estimate_fy_h",
        "earnings_fiscal_period_fy_h",
        "earnings_release_date_fy_h",
    ],
}
'''


def render(catalog: dict[str, Any]) -> str:
    out = [_HEADER]
    out.append("# {statement: [base field ids to request]} — union across templates.")
    out.append("STATEMENT_REQUEST_FIELDS: dict[str, list[str]] = " + _pyfmt(catalog["request"]))
    out.append("")
    out.append("# {statement: {fund_view_mode: [base ids in display order]}}.")
    out.append("STATEMENT_ORDER: dict[str, dict[str, list[str]]] = " + _pyfmt(catalog["order"]))
    out.append("")
    out.append("# {base field id: display label}.")
    out.append("FIELD_LABELS: dict[str, str] = " + _pyfmt(catalog["labels"]))
    out.append("")
    return "\n".join(out)


def _pyfmt(obj: Any, indent: int = 0) -> str:
    """Deterministic, readable Python literal formatting."""
    pad = "    " * (indent + 1)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        lines = ["{"]
        for k, v in obj.items():
            lines.append(f"{pad}{k!r}: {_pyfmt(v, indent + 1)},")
        lines.append("    " * indent + "}")
        return "\n".join(lines)
    if isinstance(obj, list):
        if not obj:
            return "[]"
        # short lists inline
        rendered = ", ".join(repr(x) for x in obj)
        if len(rendered) <= 96:
            return "[" + rendered + "]"
        lines = ["["]
        for x in obj:
            lines.append(f"{pad}{x!r},")
        lines.append("    " * indent + "]")
        return "\n".join(lines)
    return repr(obj)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    snapshot = json.loads(Path(sys.argv[1]).read_text())
    catalog = build(snapshot)
    Path(sys.argv[2]).write_text(render(catalog))
    n = {k: len(v) for k, v in catalog["request"].items()}
    print(f"wrote {sys.argv[2]} — request bases per statement: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
