# Project status

## In development: WITS0 real-time integration

The first raw-capture boundary is implemented: TCP server/client, client reconnect, incremental
`&& ... !!` decoding, append-only `*.wits`, a UTC `*.chunks.jsonl` index, replay, and a modeless
monitor. The built-in GeoScape GSWITS profile schema v1 contains 11 records and 105 fields. The
next slice is parsing, Import Review, and append-only AcquisitionSession commit; mapping still
requires confirmation with real raw data.

## In development: offline WITSML 2.x inventory

Safe, read-only inspection is implemented for individual XML/WITSML files, directories, and
ZIP/EPC packages. The dialog shows top-level objects, `schemaVersion`, UUIDs, references, and,
for each `Channel`, mnemonic, data type, unit, source, class, indexes, and range. Archives are
never extracted; traversal, DTD/entity declarations, encryption, duplicate paths, and resource
limit violations are rejected. This slice does not create a `Dataset`, read channel arrays, or
connect through ETP.

## In development: GeoScape II GS2

Safe container validation and selected inner-table import through the existing Paradox reader,
Import Review, and `Dataset` are implemented. The СГ-8 sample contains 13 recognized Paradox 7.x
tables; `GS2#101.db` has TIME, DEPTH, and 206 channels on a 0.2 m grid. The five
`GS2#1…GS2#1_4` parts are automatically merged into a validated 4,338,103-row TIME series.
`GS2.mdb` is read through a read-only Qt ODBC/ACE adapter: imports receive `WELLS`,
`FORMULAS.RESGID → S-code` mappings, Sensors fallback, and audit metadata. A missing driver no
longer blocks table import and produces actionable diagnostics.


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
