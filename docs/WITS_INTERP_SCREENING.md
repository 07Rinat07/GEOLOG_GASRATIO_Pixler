# WITS-INTERP-01 — preliminary fluid-screening projection (P0)

This is a **headless, presentation-only first slice**, not the completed WITS
interpretation UI. It does not read or change WITS/LAS, source Dataset, the
Haworth/Pixler calculation profiles, geological observations or thresholds.

`project_wits0_fluid_screening` accepts an existing
`GasRatioAssessment`, optional `PixlerAssessment`, the already evaluated
wetness robust-Z value, and an independently determined
`Wits0GasOriginKind`. It calls the existing
`conservative_fluid_hypothesis` and `fluid_phase_from_hypothesis` rather
than adding a second calculation or claiming an independently proven fluid.
Insufficient/partial Pixler support cannot silently promote a specific oil
subtype. Unknown hypothesis codes map to indeterminate.

The returned immutable projection exposes:

- one stable `palette_key` to be shared by a future badge and plot stripe;
- a localized RU/KK/EN caption explicitly beginning with *preliminary
  indicator*;
- the original conservative hypothesis and assessment profile IDs;
- `formation_show_marker` **only** when the separate gas-origin assessment
  already says `FORMATION_SHOW`. Connection, trip, circulated and unknown
  gas never become formation shows solely because of fluid composition.

This service does **not** join adjacent samples into intervals, draw
notifications, assign physical colours, create geological interpretations,
claim reservoir productivity, or pass field acceptance. The next independent
WITS-INTERP-01 slices must use validated axis/source provenance before
interval coalescing and UI plotting, and must test synthetic partial evidence
and real operator/Windows acceptance separately.

Regression command:

```bash
python -m pytest tests/test_wits0_fluid_screening.py tests/test_gas_ratio_interpretation.py -q
```

Before merging, require Ruff, mypy and the three mandatory Windows Release Gate
jobs completed/SUCCESS on the exact PR HEAD and exact current main HEAD.
Recheck both heads and mergeability, squash at most one PR, then require all
three post-merge Windows jobs on the new main SHA. A green rerun does not
establish the root cause of native Qt crash #544; physical printing and field
validation remain open.
