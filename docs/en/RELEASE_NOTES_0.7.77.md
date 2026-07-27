# GEOLOG GASRATIO@Pixler 0.7.77 — WITS0 live monitor

## Slice purpose

Version 0.7.77 completes the main part of stage E of the WITS0 integration. A read-only
`AcquisitionLiveView` projection and a **Monitor** tab now operate over the growing
`AcquisitionDataset` and append-only `AcquisitionSession`.

## Current values

The current-values table shows selected channels, the latest finite value, unit, and quality state.
When the newest row has no value for a channel, the previous finite value remains visible but is
explicitly marked as “no new value”. Supported states are `good`, `missing`, `invalid`,
`source_gap`, and `stale`.

## Time and depth graphs

- a real time/depth Dataset index is used directly;
- a time-index Dataset can derive a read-only depth axis from a reviewed `HOLE_DEPTH`, `BIT_DEPTH`,
  `MD`, `GAS_DEPTH`, or other semantically recognized depth curve;
- a depth-index Dataset can derive a UTC time axis from `AcquisitionRecord.received_at`;
- derived axes do not mutate the Dataset and are not persisted into the project;
- displayed channels can be changed without stopping acquisition.

## Live, pause-view, and history

Auto-follow keeps the right window boundary at the newest point. **Pause view** freezes only the
visible row boundary while `Wits0AcquisitionRuntime` continues accepting, normalizing, and appending
data. Resume catches up to the current tail. With auto-follow disabled, plot pan/zoom defines the
history window.

## Downsampling and quality markers

Every visible series uses the shared peak-preserving `select_visible_samples()` implementation,
which retains NaN breaks and enforces a rendering budget. The graph shows source-sequence gaps,
abnormally large axis intervals, invalid source values, and missing-value spans.

`AcquisitionRecord.source` now also retains sequence status, raw SHA-256, and structured quality
codes per WITS `record/item`.

## Compatibility and verification

Project format remains **v20**, form schema **v8**, and tablet layout **v18**. Existing projects
require no migration. Compact 50% columns, ready 48/80 widths, all ready and user forms, Create form,
Save user form, duplicate and whitespace name protection, Ctrl+S save, and reopen behavior remain
unchanged.

Full Qt runtime verification still requires Windows with PySide6/pyqtgraph and a real anonymized
GSWITS raw stream. Pause affects presentation only and is not a replacement for controlled close.
