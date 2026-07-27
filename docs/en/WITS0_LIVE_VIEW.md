# WITS0 live monitor

## Purpose

The **Monitor** tab renders a read-only projection of the growing WITS0 Dataset. It does not mutate
`AcquisitionSession`, stop TCP intake, or bypass `AcquisitionController`.

## Current values

The user selects channels on the left. Each row shows the latest finite value, unit, and quality.
If the newest row has no channel value, the previous finite value remains visible with a `missing`
state. The `stale` state is calculated from the UTC reception timestamp.

## Time and depth axes

**Automatic** uses the active Dataset index. **Time** and **Depth** use a real index when available.
When a secondary axis is absent, the live monitor creates a read-only axis only:

- UTC time from `AcquisitionRecord.received_at`;
- depth from a reviewed semantic depth curve.

A derived axis is not added to the Dataset and is not persisted in the project.

## Auto-follow, pause-view, and history

Auto-follow displays a configured trailing window ending at the newest point. Disabling it enables
history pan and zoom. **Pause view** freezes the visible row count while acquisition continues to
accept and append data. Resume catches up to the current tail.

## Downsampling

`select_visible_samples()` limits points in the selected window while retaining peaks and NaN
breaks. The source Dataset and append-only records remain unchanged. The footer reports source and
rendered point counts.

## Quality and gap markers

The plot displays source-sequence gaps, large axis intervals, invalid values, and missing spans.
Marker provenance comes from append-only records. Markers are diagnostic support and do not replace
mud-logging specialist decisions.

## Limitations and acceptance

Channels with different physical units currently share one value scale; separate tracks remain a
future improvement. Selected-channel and history-window settings are not yet persisted in the
workspace. A Windows Qt smoke test and validation with real anonymized GSWITS raw traffic remain
mandatory.
