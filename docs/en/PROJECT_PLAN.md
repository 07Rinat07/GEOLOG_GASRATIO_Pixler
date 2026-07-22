# Project plan


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
