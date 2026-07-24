# Versioned lag/depth correction

Status: implemented in 0.7.44. Introduced in project format v19; current project format v20.
Lag correction schema: v1.

## Purpose

The correction maps a surface measurement to the calculated arrival depth of gas, cuttings, or
another channel. The source acquisition dataset and append-only journal remain unchanged. Each
correction is materialized as a separate `DatasetKind.DERIVED` with two axes:

- **source depth** — the original recorded depth;
- **corrected depth** — depth after the selected lag profile.

## Calculation methods

- `constant_time` — a constant delay in seconds;
- `annular_volume_flow` — delay from `annular_volume_m3 / flow_rate_m3_per_s`;
- `pump_strokes` — calculation from annular volume, pump output, and strokes per minute;
- `control_points` — piecewise-linear `row → corrected depth` control points.

TIME-based methods require explicit TIME and DEPTH indexes. Repeated time values are handled only
through the selected `TimeDepthAggregationPolicy`. Corrected depth remains `NaN` outside the
supported interpolation range; hidden extrapolation is not performed.

## Revisions and provenance

`LagCorrectionProfile` stores ordered immutable revisions. A revision records the method,
parameters, indexes, curve IDs, aggregation policy, source row count, source/output SHA-256,
acquisition sequence/audit digest, formula ID/version, UTC time, author, and comment. A new
revision creates a new output dataset and never overwrites the previous result.

The source fingerprint protects the historical row prefix that was actually used. New append-only
rows are allowed, while changes to historical values, metadata, or a materialized output are
detected when the project is loaded.

## User workflow

1. Select the source dataset.
2. Open **Calculations → Lag/depth correction...**.
3. Select or create a profile and channel purpose.
4. Choose TIME/DEPTH indexes and a calculation method.
5. Enter method parameters, author, and the new revision comment.
6. Review source depth, corrected depth, and lag in preview.
7. Create the revision and activate it when required.
8. Open the derived dataset on the source or corrected axis.

`ReportDefinition` stores the selected index explicitly, so preview, export, and reporting cannot
switch coordinates silently.

## Saving, rollback, and reopen verification

Profiles and revisions are part of the project. Press **Ctrl+S** after creating or activating a
revision. Closing without saving discards current-session changes. Reopen the project and verify
the active revision, selected axis, source/output fingerprints, and derived dataset. Activating an
older revision does not delete newer revisions.

## Limits and checks

- the source acquisition dataset must remain unchanged;
- implicit units and hidden extrapolation are not allowed;
- TIME/DEPTH, duplicate, and range warnings must be resolved before creating a revision;
- report and export must use the explicitly selected axis;
- compare several control depths with a manual calculation before operational use.

## Migration

Project format v19 adds `well.lag_correction_profiles`. Migration `v18 → v19` creates an empty
collection without changing datasets, acquisition sessions, operational events, or tablets.
