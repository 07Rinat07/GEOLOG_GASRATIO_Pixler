## Version 0.7.27 — deletion and current-form annotation scope

Fixes annotation deletion from the context menu and focused editor. Comments, callouts, curve values and images now have a stable scope for the current dataset and tablet form, so they do not appear in other forms. Legacy objects without a scope are bound automatically to the saved form. Screen, PDF and Masterlog use the same filtering.

## Version 0.7.26 — typed batch DB → LAS plan

Fixes the Windows `'str' object has no attribute 'value'` failure after manual index configuration. `ParadoxImportPlan` now normalizes Qt/JSON values and prevents string pseudo-enums from entering the importer. Diagnostics include the operation stage. A 0.4 m source step is valid and does not conflict with the 0.2 m nominal standard.

## Version 0.7.25 — in-batch index configuration and safe annotation rendering

The batch converter no longer reports an ambiguous index as a generic failure. The row becomes “Configuration required”; the user selects depth/time in the normal import dialog and retries only that file. The full-size translucent annotation QWidget has been removed. Visible objects are rendered as small independent sprites, while the hidden manager paints nothing over PyQtGraph. This remains a test build until Windows verification.

## Version 0.7.24 — Windows render test hotfix

Fixes the black-tablet regression by restricting the annotation overlay native region to visible annotation bounds. The package remains a test build until it passes the Windows GUI smoke test.

# Project status

## Version 0.7.23 — OOP tablet routing and restored editing

Pointer/keyboard handling is split between `TabletInteractionRouter`, the annotation tool, track editor, F4 mode coordinator and lost-release watchdog. The paint overlay is permanently mouse-transparent and can no longer cover the plots. Direct annotation creation, selection, drag/resize and editing are restored together with track selection, right-click menus and the full curve/parameter column editor. The DB → LAS batch workflow now exposes full output paths and explicit open/retry/close actions.

## Version 0.7.21 — smooth callout/comment editing

The annotation layer no longer rebuilds the tablet after every drag. During a gesture only the object footprint is repainted, the native mask is not reapplied per pixel, and geometry/Undo is committed once on release. Selecting an object without movement creates no project change.

## Version 0.7.20 — unified time and direct F4 annotations

All user-facing time values pass through one `DD.MM.YYYY HH:MM:SS` formatter. Tablet views, the LAS table, time curves, Paradox import, annotations and printable inspections no longer depend on Windows/Linux timestamp behavior. Annotations are created by direct graph click, freely moved/resized by mouse and clipped below track headers.

## Version 0.7.19 — annotations follow depth and time

Fixed the tablet-wide annotation layer becoming detached from the vertical axis. Scrolling, panning, go-to and zoom remap the data anchor into current screen coordinates while preserving the box offset and size. The project format is unchanged.

## Version 0.7.18 — free annotations and responsive DB → LAS

Annotations now use one tablet-wide overlay; Paradox import populates UI tables in slices and exposes a visible footer, six-stage progress and safe cancellation.

## Version 0.7.17 — annotation interaction hotfix

Fixed F4 actions, the focused editor, pointer-event routing, drag, resize, double-click editing and context menus for callouts/comments. The GeoScape 0.2 m standard is now shown separately from a file’s actual row step; `BLData.db` retains its real LAS `STEP=0.4` until an explicit resampling operation is requested.

## Version 0.7.16 — GeoScape/Paradox DB import

A bounded binary Paradox reader now validates `.db`, discovers same-name `.PX/.TV/.FAM` files case-insensitively, and opens sources read-only. Imported data enters the existing multi-index `Dataset` model rather than a second editor, so the standard table, graphs, project storage, and LAS export remain in use. The release adds asynchronous preview, depth/time selection, exact-schema profiles, a user channel dictionary, quality control, depth/time LAS, TIME → DEPTH, and batch conversion.

Validation read `BLData.db` as 3488 rows/70 fields and `D250.db` as 1739 rows/101 fields with no critical errors and unchanged source SHA-256 hashes. Full GUI and actual LAS round-trip validation remains required in the Windows environment with project dependencies installed.

## Version 0.7.15 — professional annotation layer

F4 now exposes compact Callout, Comment and Image commands, while the graph context menu creates an object at the exact selected coordinate. One well-scoped model supports depth, time, track and curve anchors. The unified editor controls typography, colors, fill, border, leader, arrow, shadow, geometry, locking and print permission. A curve value can be inspected and persisted as an editable print label.

Screen, preview, PDF and printing consume the same model. Annotations remain with the well through LAS merge creation and merge Undo/Redo. Legacy depth notes remain compatible. `compileall` passes; Qt GUI, HiDPI and physical-print smoke tests still require Windows with PySide6.

## Fix 0.7.13 — compact cursor and reliable edit history

The pencil cursor is now a compact 26×26 image whose hotspot matches the graphite tip. Connect points is a permanent visible mode rather than a compressed combo-box entry. Undo/Redo are available on the pencil bar and track context menu, while Ctrl+Z/Ctrl+Shift+Z work regardless of widget focus. Dependent curves recalculate immediately in memory; disk persistence still requires explicit Save.


## Fix 0.7.12 — persistent pencil cursor and live values

The pencil cursor now remains visible in the selected track. A floating card shows the mnemonic, depth/time, proposed value and previous value and stays visible while the pointer remains inside the plot. Dependent curves recalculate immediately in memory, while disk persistence still requires explicit Save.

## 0.7.11 fix — pencil, Constructor and reference Masterlog

Freehand and point modes work in the tablet; failed edits keep their preview, dependants recalculate immediately and saving remains explicit. Every Constructor section is readable under a dark application palette.

## 0.7.10 fix — readable captions and safe saving

Legacy codes such as `S300`, `S720`, `S800`, `S900` and `S50` are resolved through Sensors.DB and displayed as readable names. The source mnemonic remains available in tooltips/editors. Pencil edits apply and recalculate dependants immediately in memory, mark the project with `*`, and are written only by the Save action. Validation: `1017 passed, 1 skipped`; Ruff and `compileall` pass.

## 0.7.9 fix — curve pencil

The pencil is now a native tablet tool. Its target selector is always visible, the selected track scrolls into view, the left button draws an orange preview, and releasing the mouse commits through the shared command history. Validation: `1012 passed, 1 skipped`.


## 0.7.8 fix — Form Library

Section and form names no longer disappear on white surfaces when the application uses a dark palette. Factory presets, user folders, details and button captions remain readable. The JSON repository format is unchanged. Full validation: `1009 passed, 1 skipped`; Ruff and `compileall` pass.

## Version 0.7.7 — Unified Workspace

- primary workflows use direct buttons instead of inconvenient drop-down menus;
- `F4` toggles the form add/edit/move/remove/save toolbar;
- the Form Library separates factory and user depth/time forms;
- user forms are stored physically in `depth` and `time` directories;
- factory presets open as editable working copies;
- the Constructor exposes ready Masterlog headers in a visible gallery;
- advanced settings are collapsible and actions include tooltips;
- Windows lossless LAS export with Cyrillic descriptions is fixed.

Validation: `1008 passed, 1 skipped`; Ruff and `compileall` pass. A final visual Windows and physical-printer smoke test remains.

## 0.7.5 template — ready geological-technological survey blank

- an A3 landscape preset based on the supplied reference was added;
- two optional logo slots are loaded from the header editor;
- empty logo slots do not block preflight or printing;
- coloured scales, minima/maxima and grid divisions are stored in the template;
- rock descriptions remain manual-only.

## 0.7.3 fix — LAS isolation

### 0.7.4 fixes

- Excel headers now show readable names, mnemonics and units;
- the `Parameters` sheet provides a complete mapping and resolution status;
- RU/KK/EN output and LAS mojibake cleanup are applied.


- A newly opened LAS gets a clean separate well.
- Geological intervals from the previous well do not carry over.
- Rotated text remains wholly inside its interval.

Date: 21 July 2026

The current slice is **Universal Constructor 0.7.5: KazGeology ready blank**, manual-entry editors based on the supplied
GeoData guide, and unified re-editing of geological intervals.

Completed:

- Geology, Technology, and Gas Data sections aligned with the supplied working screen;
- one depth coordinate and one parameter-header height across all tracks;
- a curated library containing the depth workspace, Masterlog, and time engineering control;
- creation, re-editing, and deletion of lithology;
- one editor for cuttings composition, colour-coded LBA 1–5, calcimetry with automatic residue, and rich description;
- updating the existing record under the same `sample_id` without duplicates;
- an absolute-gas column with `TG_CALC`, `C1`, `C2` and a separate relative-composition column with `C1_REL`–`C5_REL`;
- a fully missing gas sample remains `NULL/NaN` instead of becoming a false zero;
- adaptive main-window geometry, horizontal scrolling, and a collapsible inspector;
- correct curve gaps for NULL/NaN;
- normal save through diskette/`Ctrl+S` and Save As through `Ctrl+Shift+S`;
- synchronized RU/KK/EN documentation and interface strings.

Remaining work: unify screen and print form designers, complete the report-header editor, and finish
automatic Gas Ratio/Pixler interpretation.

## Editable captions and stratigraphy

Every track is fully editable from its right-click menu: title, section, width, X axis, parameters,
captions, styles, scales, and ranges. Stratigraphy now has a project catalog, `Shift + left drag`,
a dedicated toolbar mode, double-click editing, and project persistence. See [Editable form captions
and stratigraphy](FORM_CAPTIONS_AND_STRATIGRAPHY.md).

Current slice verification: `932 passed, 1 skipped`; Ruff and compileall pass.

## LAS Editor 2 — current status

Implemented safe ascending copies, progressive merging, direct external-curve insertion, source
manifests, guarded Undo/Redo, pencil editing, synchronous recalculation, and table exports.

### Graphical pencil fix (slice22)

The editor now provides explicit source LAS-curve selection, a toolbar button, tablet context-menu entry, a dedicated pencil cursor and an orange preview stroke. Calculated curves are excluded from direct editing; dependent parameters are recalculated after source-data changes.

## Constructor 0.7.1

The Constructor is embedded in the application and reuses Form Manager and the Masterlog
renderer. Assets are packaged inside the project rather than shipped as an external overlay.
Searchable resources, WYSIWYG headers, page profiles, images, dynamic legends, semantic depth
symbols with X/Y offsets and preflight are implemented. See [Constructor guide](CONSTRUCTOR.md).

## Version 0.7.1: text and lithotypes

0°/±90° direction and near-top/centre/near-bottom placement now persist for stratigraphy, form
captions, header text/fields, and lithotype labels. All 117 supplied BMP patterns are available in
lithology, cuttings, and headers through one catalog. Factory rows can be overridden and reset;
project rows can be added and edited. Screen, preview, PDF, and print use the same model.

## Version 0.7.2: exact BMP lithotypes

The standard rocks now use the actual BMP patterns from the two supplied archives instead of a
flat colour. On the tablet the pattern is tiled in native device pixels and therefore remains
sharp under depth zoom. Text over the pattern is off by default and can be enabled explicitly in
the form editor. The same assets are used by cuttings, header legends, preview, PDF and print.
Full run: `1002 passed, 1 skipped`.

## Planned unified reporting

The existing calcimetry/LBA PDF will be expanded into one interval report covering lithology,
cuttings, manual descriptions, LBA, calcimetry, stratigraphy, C1–C5, total gas, Gas Ratio/Pixler,
H₂S/CO₂, drilling channels and events. Planned outputs are PDF/DOCX/XLSX/CSV/TSV/HTML with
preview and preflight. Automatic rock-description fallback is not allowed.

## 0.7.14

Added safe import of legacy Delphi SKF forms into an editable tablet form and linked Masterlog header. The original vendor samples are not present in the current environment, so custom classes still require field validation.
