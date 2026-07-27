# Project status

## In development: WITS0 field acceptance

The software slices for raw capture, parser, Import Review, append-only acquisition, live monitor
and reliability are implemented. Connection records, disk guard, raw retention, restart recovery,
workspace persistence and Windows soak tooling are complete. Remaining work is a real 8–24 hour
GSWITS soak, controlled low-space/disk-full exercise, independent channel scales, Windows
startup/service evaluation and a signed field checklist. The built-in GeoScape mapping still
requires confirmation against anonymized real traffic.

## Completed in 0.7.79: offline WITSML 2.x import

The safe inventory now reads embedded/relative-file `ChannelData`, selects a ChannelSet, active
time/depth index and scalar numeric channels. Import Review performs semantic mapping, strict UOM
conversion and row QC, then atomically creates a Dataset with source/data SHA-256 and a stable
digest. Binary Avro, multidimensional arrays, SOAP and ETP remain later work.

## Completed in 0.7.80: WITSML 1.4.1.1 SOAP read-only

Added a read-only Store API client for GetVersion, GetCap and GetFromStore, hierarchy browsing from
Well through LogData, bounded timeout/retry, hash-chained audit and Windows Credential Manager
password storage. Remote LogData reuses the existing WITSML Import Review and atomic Dataset
registration. Add, Update and Delete are rejected by the client boundary.

## In development: GeoScape II GS2

Safe container validation and selected inner-table import through the existing Paradox reader,
Import Review, and `Dataset` are implemented. The СГ-8 sample contains 13 recognized Paradox 7.x
tables; `GS2#101.db` has TIME, DEPTH, and 206 channels on a 0.2 m grid. The five
`GS2#1…GS2#1_4` parts are automatically merged into a validated 4,338,103-row TIME series.
`GS2.mdb` is read through a read-only Qt ODBC/ACE adapter: imports receive `WELLS`,
`FORMULAS.RESGID → S-code` mappings, Sensors fallback, and audit metadata. A missing driver no
longer blocks table import and produces actionable diagnostics.



## Completed in 0.7.78

Added stable connection IDs, an append-only fsync lifecycle journal, typed connection acquisition
records, a pre-write disk guard, inactive raw retention, an atomic recovery manifest, safe sidecar
repair, open-session restart recovery, per-well workspace persistence and Python/PowerShell Windows
soak tooling. Project format remains v20.

## Completed in 0.7.77

Added the read-only live projection with current values, time/depth axes, auto-follow, pause-view,
history/downsampling and source/axis/invalid/missing markers over the growing Dataset.

## Completed in 0.7.76

Added `Wits0FrameNormalizer`, immutable normalized measurement batches, and
`Wits0AcquisitionRuntime`. Confirmed frames pass through atomic bounded enqueue, a backpressure
policy, checkpoints, and controlled close into an append-only `AcquisitionSession`. The WITS0
window starts a session for the current well, shows pending/applied/skipped counters, and selects
the growing Dataset. Live/replay batches are deterministic, and a closed session survives project
save/reopen without a project-format change.

Snapshot: 27 July 2026. Package version: **0.7.76**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Completed in 0.7.75

Added WITS0 Import Review with an immutable discovery snapshot, every detected record/item,
Semantic Channel Dictionary binding, source and canonical UOM, time/depth index selection,
hide/rename/manual overrides, versioned custom profiles, and an atomic immutable
`AcquisitionDatasetSchema` commit. New or changed record/items mark a confirmed schema stale
without mutating raw or parser data.

Snapshot: 27 July 2026. Package version: **0.7.75**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Completed in 0.7.74

Added the typed WITS0 parser, immutable parsed models, diagnostics, and per-record sequence
tracking. Live TCP and replay share one pipeline; the capture window shows parsed fields and
anomalies. Dataset commit remains the next increment.

Snapshot: 27 July 2026. Package version: **0.7.74**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Completed in 0.7.73

A Qt-independent WITS0 source adapter and modeless **WITS Level 0 Capture** window were added.
The network worker does not block the GUI; raw bytes are stored before framing and UI queue
pressure cannot discard raw data. TCP chunks are indexed by UTC/offset/size and live/replay use
the same decoder. No Dataset is created yet.

Snapshot: 27 July 2026. Package version: **0.7.73**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Completed in 0.7.72

The top command rows were moved out of the native toolbar area into an application-owned central
responsive host, and the window minimum is capped to the active monitor work area. Symbols retain
geometry down to `0.01` logical pixel, render at no less than one device pixel, and use a separate
selection/move frame. CSV/XLSX uses the exact rows of an active numeric DEPTH/TIME index.
Automated checks are complete; manual Windows external-monitor/HiDPI/physical-print acceptance
remains open.

Snapshot: 27 July 2026. Package version: **0.7.72**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Completed in 0.7.71

Both top toolbars are hard-capped to the window width and re-adapt after F4, action-state, DPI and monitor changes. Catalog symbols truly narrow to 1×1 logical pixel while normal annotations retain the 40×24 px safety minimum.

Snapshot: 25 July 2026. Package version: **0.7.71**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Completed in 0.7.70

- the main and F4 toolbars use one constrained responsive row without native Qt overflow;
- the right-side editing control remains inside the window;
- catalog symbols can be narrowed independently to 2 logical pixels and retain their size after Ctrl+S/reopen.


Snapshot: 25 July 2026. Package version: **0.7.70**. Project format: **v20**,
form schema: **v8**, tablet layout: **v18**.

## Completed in 0.7.69

- the top toolbar selects expanded, compact, or ultra-compact mode from the actually measured
  localized button widths in Qt logical pixels;
- the fixed resolution threshold was removed: calculation includes the system font, style, and DPI;
- when even icon-only mode does not fit, lower-priority commands move into the **“⋯”** menu;
- the right-side **Form editing** toggle is not removable and remains inside the available toolbar width;
- recalculation runs after window, font, style, DPI, screen geometry/work-area, and monitor changes;
- immediate and delayed metric checks run after moving the window between a laptop and external monitor;
- user documentation, release notes, and regression tests are synchronized across RU/KK/EN.

## Retained from 0.7.68

- catalog symbols stretch independently in width and height;
- side handles resize one axis, corner handles resize both axes, and **Shift** preserves proportions;
- normal imported images remain undistorted;
- width and height participate in Undo/Redo, persist through **Ctrl+S**, restore after reopening, and
  render consistently on screen, in preview, PDF, and print.

## Retained from previous versions

Compact 44 px parameter headers without the duplicate **Scale** caption, compact geology columns,
one complete catalog of ready, **18 factory**, and user forms, the complete create/save form dialog,
and **Clear diagnostics data…** remain unchanged.

## Compatibility

Project format, form schema, and tablet layout are unchanged. Existing projects and forms require no
migration. The root `README.md` remains concise and contains no detailed fix history.
