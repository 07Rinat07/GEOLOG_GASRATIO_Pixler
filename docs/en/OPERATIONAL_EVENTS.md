# Typed operational events

Status: the event contract was introduced in 0.7.41 and remains in current project format v19.

An operational event is an immutable drilling or geological observation attached to one well
and to depth and/or time. The Qt-free contract is shared by project storage, QC, the mutation
controller, and report resolution.

## Event kinds

Six strict discriminator types are supported:

| `kind` | Payload |
|---|---|
| `drilling` | activity, ROP, RPM, WOB, hookload |
| `gas` | Total Gas, methane, ethane, propane, connection gas |
| `show` | show type, intensity 1–5, fluorescence colour, description |
| `sample` | sample code/type, bottom depth, description |
| `casing` | casing type, outer diameter, shoe depth, status |
| `formation_top` | formation code/name, confidence, description |

A payload of another kind is rejected. The codec also rejects unknown discriminators, unknown
fields, and a dictionary key that differs from `event_id`.

## Shared envelope

Each event carries stable `event_id`, `well_id`, `kind`, one or more of `depth_m`,
`elapsed_time_s`, and `measured_at`, optional `received_at`, source, positive revision,
calibration reference, typed payload, and calculated QC flags. ISO-8601 timestamps must include
a timezone and are canonicalized to UTC `Z`.

## QC schema v1

`OperationalEventQcEvaluator` deterministically recalculates a complete well collection:

- `duplicate` for equal kind, anchors, and typed payload;
- `out_of_order` when arrival order contradicts the primary coordinate;
- `gap` when the depth/time policy threshold is exceeded;
- `stale` when arrival delay exceeds the policy;
- `calibration_missing` and `calibration_expired` for calibrated channels.

Thresholds are held in immutable `OperationalEventQcPolicy`. Gas events require calibration by
default. Results do not depend on JSON key order.

## Mutation boundary

`OperationalEventController` owns create, optimistic-revision update, remove, deterministic
listing, well identity checks, and full QC recalculation after every mutation. UI and import
adapters must not mutate `Well.operational_events` directly.

## Storage in project format v19

Events are stored as `well.operational_events`, keyed by event ID. Migration `v16 → v17` adds
an empty collection to every well without changing datasets or interpretations. The decoder
reconstructs the exact payload class and rejects malformed records.

## ReportDefinition integration

`resolve_operational_event_report()` consumes an existing `ResolvedReportDefinition` and reuses
its exact inclusive bounds. Depth, relative-time, and datetime indexes map to `depth_m`,
`elapsed_time_s`, and UTC `measured_at` respectively. A `DRILLING` section selects drilling
events. An `EVENTS` section selects all kinds or a comma-separated `event_kinds` option.

Append-only growing datasets, checkpoints, and deterministic replay were completed in 0.7.42.
Events replay through the same revision/QC controller and retain the same fingerprint. The next
slice is versioned lag/depth correction without modifying the source journal. See
[Acquisition replay](ACQUISITION_REPLAY.md).
