# Versioned lag/depth correction

Status: implemented in 0.7.44. Introduced in project format v19; current project format: v20. Lag correction schema: v1.

The correction maps a surface measurement to its calculated arrival depth without modifying the
recorded acquisition dataset or append-only journal. Each immutable profile revision materializes a
separate derived dataset containing both the source and corrected depth axes.

Supported methods are constant time, annular volume divided by flow rate, pump output/strokes, and
manual row-to-depth control points. TIME-based methods require explicit TIME and DEPTH indexes and
an explicit repeated-time aggregation policy. Values outside the supported interpolation range stay
`NaN`; hidden extrapolation is not performed.

A revision records parameters, indexes, curve IDs, source row count and fingerprint, output digest,
acquisition sequence/audit provenance, formula ID/version, UTC timestamp, author, and comment. A
new revision creates a new output dataset. Appending new source rows is allowed, while changing the
historical source prefix or a materialized output is rejected during project loading and replay.

Use “Calculations → Lag/depth correction...” to create or revise a profile, preview source/corrected
depth, activate an older revision, and open the derived dataset on either axis. `ReportDefinition`
stores the selected index explicitly.

Project format v19 adds `well.lag_correction_profiles`; migration `v18 → v19` adds an empty
collection without changing existing project data.
