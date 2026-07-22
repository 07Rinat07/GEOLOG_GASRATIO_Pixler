## 0.7.27 snapshot

1. Windows: create a comment and callout, then delete through the context menu, Delete key, full manager and focused editor.
2. Open another form for the same dataset and verify that unrelated annotations are absent.
3. Return to the original form and verify object, geometry and style restoration.
4. Save the current tablet as a user form and verify annotation-scope rebinding.
5. Compare screen, PDF and Masterlog output; do not promote TEST to stable without a real GUI smoke-test.

## 0.7.26 snapshot

1. Windows: D1174/D250 → manual depth/time configuration → retry the batch operation.
2. Verify no `.value` failure and complete `DB → LAS → reopen`.
3. Verify actual `STEP=0.4` is preserved.
4. Verify explicit 0.2 m resampling separately without modifying the source DB.

## 0.7.25 snapshot

1. Verify the batch flow: ambiguous DB → Configure selected DB → select depth/time → retry → open LAS.
2. Verify a populated tablet on Windows before and after F4; the graph body must never become black.
3. Verify comments/callouts across tracks, scrolling, resizing, PDF and printing.
4. Do not promote the TEST build to stable without a real Windows GUI smoke-test.

## 0.7.24 snapshot

A stable release is blocked until the Windows GUI smoke test and visual non-empty tablet-render checks pass before and after F4 activation.

# Project plan

## 0.7.23 snapshot

- [x] one OOP pointer/keyboard interaction router;
- [x] separate annotation, track, F4 mode and watchdog classes;
- [x] paint-only overlay without native pointer grab or widget mask;
- [x] restore annotation creation, selection, drag/resize and editing;
- [x] restore track selection, menus and full column editing;
- [x] complete the user-facing DB → LAS batch workflow;
- [x] add unit/source-contract tests for architecture invariants;
- [ ] run Windows/HiDPI smoke tests and the full LAS round-trip.

## 0.7.21 snapshot

- [x] remove full tablet refreshes from annotation editing;
- [x] repaint only the annotation dirty region;
- [x] cache the native mask and commit geometry once;
- [x] create no history/dirty state for a click without movement;
- [ ] verify smooth interaction on Windows and HiDPI.

## 0.7.20 snapshot

- [x] one cross-platform date/time format;
- [x] NumPy datetime, Unix, Delphi/OLE and elapsed time;
- [x] direct click-to-create F4 annotations;
- [x] clipping below headers and eight resize handles;
- [ ] Windows smoke test, PDF and physical printing.

## Slice 0.7.19 — synchronize annotations with the axis

- [x] remap screen anchors after scrolling and zooming;
- [x] cover both shared-camera and direct ViewBox range paths;
- [x] preserve saved offsets, size and style during navigation;
- [x] reuse overlay graphics objects instead of rebuilding every wheel step;
- [ ] run the Windows smoke test on depth/time tablets, PDF and printing.

## Slice 0.7.18 — stabilize interaction and import

Run the Windows smoke test for annotations, PDF/print and safe Paradox cancellation on large tables.

## Slice 0.7.17 — annotation interaction hotfix

- [x] restore F4 actions and the focused Save/Cancel editor;
- [x] restore drag/resize, double-click editing and context menus;
- [x] add event-routing regression coverage;
- [x] separate the GeoScape 0.2 m standard from the actual DB row step;
- [ ] run the full Windows, PDF and physical-print smoke test.

## Slice 0.7.16 — GeoScape/Paradox DB import

- [x] detect Paradox from binary structure and reject SQLite/random DB files;
- [x] read schema, blocks, and records with bounds checks, cancellation, and field diagnostics;
- [x] discover DB/PX/TV/FAM bundles without requiring companions;
- [x] map data into the existing `Dataset` model and retain unknown channels;
- [x] score depth/time candidates and support OLE/Delphi, Unix, and relative time;
- [x] add preview analysis, profiles, dictionary, quality control, and explicit duplicate rules;
- [x] add depth/time LAS, TIME → DEPTH, and batch conversion;
- [x] test `BLData.db`, `D250.db`, synthetic, SQLite, and invalid files;
- [x] synchronize RU/KK/EN UI and documentation;
- [ ] run the full Qt smoke test and actual LAS round-trip on Windows with `lasio`.

## Slice 0.7.15 — professional annotation layer

- [x] one backward-compatible versioned model instead of simple depth notes;
- [x] callout, comment, curve value, image and symbol objects;
- [x] depth, time, track and curve anchors;
- [x] compact F4 toolbar, graph context creation, double-click edit, drag and resize;
- [x] complete appearance editor and independent print flag;
- [x] one model for screen, PDF, printer and direct Masterlog rendering;
- [x] persistence through LAS merge and merge Undo/Redo;
- [x] RU/KK/EN documentation and tests;
- [ ] Windows HiDPI/PDF/physical-print smoke test.

## Slice 0.7.13 — compact pencil, visible points and Undo/Redo

- [x] replace the long cursor with a compact 26×26 pencil using the graphite tip as its hotspot;
- [x] expose Freehand and Connect points as permanent buttons;
- [x] apply selected points with Connect, Enter or a double-click on the last point;
- [x] add dedicated Undo and Redo buttons to the pencil bar;
- [x] make Ctrl+Z and Ctrl+Shift+Z application-wide;
- [x] recalculate dependent curves in memory and persist only on explicit Save.


## Slice 0.7.12 — persistent pencil and live values

- [x] prevent Qt/pyqtgraph from replacing the pencil cursor with the default arrow;
- [x] show depth/time, proposed value and previous sampled value beside the pointer;
- [x] keep the card visible while stationary and restore it after a plot refresh;
- [x] recalculate dependants immediately in memory and persist only on explicit Save.

## Slice 0.7.11 — connected points, reference Masterlog and Constructor contrast

Add freehand and connected-point pencil modes, acknowledged edits, immediate in-memory dependent recalculation without automatic disk writes, an explicit high-contrast Constructor theme and a visible reference Masterlog with two replaceable logos.

## Slice 0.7.10 — readable parameter captions and explicit pencil saving

- [x] resolve vendor `S<number>` codes through the Sensors.DB `legacy_gid` reference;
- [x] show a readable graph caption while retaining the original mnemonic in tooltips and editors;
- [x] prevent old `display_name=S300` values from suppressing a new catalog translation;
- [x] prefer an explicit LAS description when a vendor reuses an S-code for another channel;
- [x] activate the pencil for the selected curve and mark the target track with `✎`;
- [x] recalculate dependent curves immediately in memory;
- [x] mark the project unsaved and write changes only when the diskette/Save action is pressed;
- [ ] validate the complete vendor-code set on production LAS files.

## Slice 0.7.9 — curve pencil directly in the tablet

- [x] persistent track/source-curve selector above every form;
- [x] left-button drawing without switching to a separate tab;
- [x] automatic scrolling to the target track, pencil cursor and orange preview;
- [x] linear, logarithmic and calcimetry scales;
- [x] ascending and descending vertical indexes;
- [x] Undo/Redo and dependent-curve recalculation;
- [x] calculated curves remain protected from direct editing.


## Slice 0.7.8 — visible Form Library

- [x] explicit contrasting text for the tree, search, details and buttons under a dark app theme;
- [x] visible factory/user depth and time form names;
- [x] no change to the user JSON format;
- [x] GUI regression coverage with a dark palette.

## Slice 0.7.7 — unified workspace

- [x] direct LAS Editor, Form library and Constructor buttons without incorrect drop-down menus;
- [x] F4 toggles a dedicated column, track and parameter editing toolbar;
- [x] save the live tablet as a user form with ranges, colours, scales and grids;
- [x] user forms are separated into `depth` and `time` in both UI and storage;
- [x] factory forms open as editable working copies while source presets remain protected;
- [x] the Constructor now has side navigation, a visible ready-Masterlog gallery and collapsible advanced settings;
- [x] Windows lossless LAS export with Cyrillic descriptions is fixed;
- [ ] final visual smoke test on the working Windows monitor and printer.


## Slice 0.7.6 — safe LAS Editor

- [x] separate Editor section and visible LAS Editor button (`Ctrl+Alt+E`);
- [x] creation, opening, table editing, descending-depth repair and resampling;
- [x] insert selected external LAS curves into a new copy;
- [x] splice loaded LAS datasets and save a separate file;
- [x] source files are never overwritten;
- [x] `GK:1/GK:2`, Cyrillic labels, CP866 and negative `STEP` are normalized safely.


## 0.7.3 fix — LAS isolation

## Slice 0.7.4 — readable Excel export

- [x] readable names plus technical mnemonics;
- [x] `Parameters` sheet;
- [x] RU/KK/EN, Unicode and numeric cell types.


- A newly opened LAS gets a clean separate well.
- Geological intervals from the previous well do not carry over.
- Rotated text remains wholly inside its interval.

Date: 21 July 2026

1. **GeoData Depth Workspace** — production screen with unified lithology, cuttings, LBA,
   calcimetry and manual-description editing.
2. **Masterlog and Constructor** — one controlled workflow for form, header, preview, PDF and
   physical printing.
3. **Reports and interval export** — exact lithology, cuttings, LBA, calcimetry, stratigraphy,
   manual descriptions, gas and drilling intervals in PDF/DOCX/XLSX/CSV/TSV/HTML.
   See the [detailed plan](REPORT_EXPORT.md).
4. **Gas Ratio & Pixler** — dedicated scales, controlled interpretation, markers and explanation;
   raw and calculated gas channels are included in reporting.
5. **Captions, stratigraphy and catalogs** — shared editable presentation, intervals, lithotypes,
   symbols and manual rock-description templates.
6. **Release verification** — real LAS, Windows screen matrix, physical printing, migrations and
   synchronized RU/KK/EN documentation.

## LAS Editor 2

- [x] ascending copy without modifying the original;
- [x] progressive merge with metadata preservation;
- [x] external LAS curve insertion with depth mapping;
- [x] pencil editing and synchronous recalculation;
- [x] batch table operations and exports.

## Universal Constructor 0.7.0–0.7.2

- [x] `Ctrl+Shift+K`, Form Manager, WYSIWYG header, preview and preflight;
- [x] A0–A4/Letter/Legal/custom/roll, portrait and landscape;
- [x] 117 exact BMP lithotypes and 19 symbols;
- [x] 0°/±90° and top/centre/bottom for stratigraphy, forms and headers;
- [x] one renderer for lithology, cuttings, legends, preview, PDF and printing;
- [ ] Windows smoke test, rulers/guides/Undo and explicit screen-print profile ID.

## Planned slice 0.7.3

- [ ] remove automatic lithology text from the Rock Description column;
- [ ] process the supplied field XLS/XLSX files into a reviewed template catalog;
- [ ] insert a template only after an explicit user action;
- [ ] allow project templates to be added and edited;
- [ ] start the unified interval-report model for geology, LBA, calcimetry, gases and drilling.

## Delphi SKF import — 0.7.14

- [x] bounded binary `TPF0` stream parsing;
- [x] conversion into `FormDocument` and linked `MasterlogTemplate`;
- [x] import from Form Library and Constructor;
- [x] recognised columns, curves, scales, text, lines and images;
- [ ] validate vendor-specific controls against the user’s real SKF samples.
