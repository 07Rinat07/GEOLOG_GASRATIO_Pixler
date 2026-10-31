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

The initial projection alone does **not** draw notifications, assign physical
colours, create geological interpretations, claim reservoir productivity, or
pass field acceptance.

## Acquisition-backed point attribution (third headless P0 slice)

`bind_wits0_fluid_screening_point(session, record, axis=..., screening=...)`
accepts only a row **already held in the supplied acquisition session**.
The result stores the exact well/session/dataset identity, record ID and
sequence, unchanged acquisition source audit text, the existing index value
and the already calculated immutable screening projection. It never writes
back to WITS or LAS. The provenance text is retained, not cryptographically
reverified by this adapter.

The **active** acquisition index must explicitly be MD (`IndexType.MD`,
`IndexRole.DEPTH`, `DepthDomain.MD`, unit `m`) or relative time
(`IndexType.RELATIVE_TIME`, `IndexRole.TIME`, `DepthDomain.TIME`, unit
`s`). Other depth domains, timestamp indexes, mismatched axes and
unverified units are rejected. Foreign session records, non-WITS0 records
and missing measured coordinates are rejected before publishing a point.

The same immutable point may outlive its source row in a mutable
`AcquisitionSession`. Before displaying or reusing it,
`verify_wits0_fluid_screening_point(session, point)` fails closed unless the
well/session/dataset identity and the unique stored record ID still match,
the record's original audit source and sequence are unchanged, and the
active index still has the identical verified type, units and coordinate.
Changed, duplicated, missing or foreign rows invalidate the point.
This is a synchronous **current-state check**, not an atomic acquisition
lock, independent proof of the source bytes, re-execution of fluid-screening
calculations, or confirmation of an observed coverage interval.

**One data-row coordinate is not an observed coverage span.** This
source-backed point is deliberately *not* a `Wits0FluidScreeningSample`
and cannot be coalesced into intervals. Before showing an interval, a later
source-span adapter must separately verify explicit start/end coverage and
continuity against actual source observations. No interpolation, point-to-
interval expansion, formation-show inference, UI stripe or physical
acceptance is performed in this step.

## Source-bound observed-coverage intervals (second headless P0 slice)

`Wits0FluidScreeningSample` carries an explicit exact source key, a typed
`Wits0GasContextAxis`, observed start/end coverage, an increasing source
sequence, and the existing immutable provisional screening projection.
Depth means **measured depth in metres**, elapsed time means **seconds from
session start**. The caller must verify those units and coverage against the
actual acquisition source; this API does not calculate lag, infer a sample
width, or convert TVD/TIME/feet into MD.

`coalesce_wits0_fluid_screening(samples, source_key=..., axis=...)` accepts
only samples matching the requested source and axis. It joins spans only when
their boundaries touch **exactly**, source sequences are consecutive, and
the complete projection (fluid hypothesis, profile IDs, operational origin)
is equal. Real coverage gaps, missing sequences, changed provisional class
or changed gas origin remain separate. Overlap, reordering, malformed
coordinates and mixed sources/axes raise errors rather than fabricating
continuity. A formation-show marker still derives only from the separate
origin classifier, never from the fluid composition. Original observations
and Haworth/Pixler calculations are not modified.

This is an **in-memory headless interval boundary**, not a persisted WITS
field, notification badge, plot stripe, physical palette or accepted
formation interval. Live UI wiring, colour/stripe parity, operator Windows
validation and actual source-span attribution remain separate slices.

Regression command:

```bash
python -m pytest tests/test_wits0_fluid_screening.py tests/test_wits0_fluid_screening_intervals.py tests/test_gas_ratio_interpretation.py -q
```

Before merging, require Ruff, mypy and the three mandatory Windows Release Gate
jobs completed/SUCCESS on the exact PR HEAD and exact current main HEAD.
Recheck both heads and mergeability, squash at most one PR, then require all
three post-merge Windows jobs on the new main SHA. A green rerun does not
establish the root cause of native Qt crash #544; physical printing and field
validation remain open.
