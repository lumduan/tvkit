---
name: Feature Request
about: Propose a new feature or enhancement for tvkit
title: "[Feature] <short description — e.g. Add support for date-range filtering in scanner API>"
labels: enhancement
assignees: ''
---

## Feature category

<!-- What part of tvkit would this feature affect? Check all that apply. -->

- [ ] Chart / OHLCV API
- [ ] Scanner API
- [ ] WebSocket / streaming
- [ ] Data export / processing
- [ ] Documentation
- [ ] Other

---

## Problem statement

<!-- What problem or limitation are you running into today?
     Describe it from a user perspective, not in terms of implementation.
     Example: "There is no way to filter scanner results by a custom date range,
     so I have to fetch all rows and filter client-side." -->

---

## Use case

<!-- What real workflow would this feature enable or improve?
     Be specific: what are you building? What does the absence of this feature force you to do instead?
     Example: "I am building a daily momentum screener that runs after market close.
     Without date-range support I cannot limit scanner results to the current session,
     which returns far more data than I need and slows down my pipeline." -->

---

## Proposed solution

<!-- How do you think this should work?
     Describe the API or behaviour you would like to see.
     If you are unsure how the API should look, describe the desired behaviour instead — a code sketch is not required.
     If this feature might introduce breaking changes to existing APIs, parameters, or return types, please mention them here. -->

```python
# Example sketch (optional — delete if not applicable)
async with ScannerService() as scanner:
    results = await scanner.scan(
        market="america",
        columns=ColumnSets.BASIC,
        date_range=("2026-01-01", "2026-03-01"),  # proposed new param
    )
```

---

## Alternatives considered

<!-- What workarounds or alternative approaches have you tried or considered?
     Why are they insufficient?
     Example: "I tried filtering after fetch but the round-trip latency and payload size
     make this impractical for real-time pipelines." -->

---

## TradingView reference (if applicable)

<!-- If this feature relates to TradingView functionality, include any relevant links:
     - TradingView Pine Script or REST API documentation
     - Screenshots of TradingView UI behaviour you want tvkit to expose
     - Undocumented parameters or endpoints you have observed
     If not applicable, write "N/A". -->

---

## Additional context

<!-- Anything else that would help evaluate this request:
     - Related issues or PRs
     - Data samples or example outputs
     - Priority / urgency for your use case -->

---

## Willingness to contribute

<!-- Would you be willing to implement this feature or help with it? -->

- [ ] I am willing to submit a pull request for this feature
- [ ] I can help with testing and feedback, but not implementation
- [ ] I am requesting this feature only — I am not able to contribute code
