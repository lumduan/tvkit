# Financial Statements

How tvkit models TradingView's fundamentals data: transport, the field catalog, period alignment, and units.

## Transport

Fundamentals are delivered over the same WebSocket the chart uses (`wss://data.tradingview.com`), as **quote fields** — not a REST endpoint. `FundamentalsClient` opens a socket, sends `quote_set_fields` with the field ids for the requested statement, collects the `qsd` (quote-symbol-data) frames, and closes. The server closes a quote-only socket after one snapshot, so each `get_*` call uses a fresh connection.

Anonymous access is sufficient: the wire returns the full statement history (20 fiscal years for most issuers), regardless of account tier. The lock icons in the TradingView web UI are a display overlay, not a server-side restriction.

## The Field Catalog

Each statement row corresponds to a TradingView field id such as `total_revenue` or `net_income`. tvkit ships a curated catalog (`tvkit/api/fundamentals/catalog.py`), generated from TradingView's field dictionary, that maps each statement to:

- the set of field-id bases to request, and
- the display order per issuer template.

Driving row selection from the catalog avoids a real hazard: TradingView ships near-duplicate ids across categories. For example, the income-statement "Non-controlling/minority interest" row is `minority_interest_exp`, while `minority_interest` is a **balance-sheet** field with different values; likewise the income-statement total is `total_non_oper_income`, not `non_oper_income` ("excl. interest expenses"). Selecting by name-substring would silently return the wrong line.

## Issuer Templates

TradingView renders different statements for different business types, identified by the payload's `report_type`: `industrial`, `banking`, `insurance`, or `other`. A bank's income statement has `net_revenue`, `interest_income_net`, and `loan_loss_provision` and **no** cost-of-goods line; an industrial company has `cost_of_goods` and `gross_profit`. `FinancialStatement.report_template` records which template applied, and any row the issuer does not report is simply absent from `lines`.

## Period Alignment

Values arrive as history arrays (field ids ending in `_h`) that are index-aligned to two parallel arrays:

- `fiscal_period_fy_h` → the period labels, e.g. `["2025", "2024", …]` (newest-first)
- `fiscal_period_end_fy_h` → the period-end Unix timestamps

tvkit parses these into `FiscalPeriod` objects with UTC `period_end` datetimes. Periods are fiscal, not calendar — Airports of Thailand ends its fiscal year in September, Toyota in March — and tvkit preserves the fiscal label. Quarterly (`FQ`), half-year (`FH`), and trailing-twelve-month (`TTM`) variants use the corresponding suffix.

## Units and Currency

All values are **raw** numbers in the issuer's reporting currency (`FinancialStatement.currency`, e.g. `THB`, `USD`, `JPY`). The TradingView UI abbreviates them as K/M/B for display; tvkit returns the full-precision figure. `None` in a value list means the field was not reported for that period — it is never a substitute for zero.

## Revenue Segments

Segments are structural fields (`revenue_seg_by_business_h`, `revenue_seg_by_region_h`) delivered as period-keyed objects: each period carries a list of `{label, value}` cells. Labels are issuer-specific strings, localized to the client's `language`, and the label set is a union across periods — an old segment label may appear only in older years. tvkit models these as `SegmentReport.by_business` and `by_region`.

## See Also

- [Fundamentals Guide](../guides/fundamentals.md)
- [Fundamentals Reference](../reference/fundamentals/index.md)
- [Symbols Concept](symbols.md)
