# Project plan

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
