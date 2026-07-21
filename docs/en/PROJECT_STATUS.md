# Current project status

## 0.7.3 fix — LAS isolation

- A newly opened LAS gets a clean separate well.
- Geological intervals from the previous well do not carry over.
- Rotated text remains wholly inside its interval.

Date: 21 July 2026

The current slice is the **GeoData Depth Workspace**, manual-entry editors based on the supplied
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
Full run: `988 passed, 1 skipped`.

## Planned unified reporting

The existing calcimetry/LBA PDF will be expanded into one interval report covering lithology,
cuttings, manual descriptions, LBA, calcimetry, stratigraphy, C1–C5, total gas, Gas Ratio/Pixler,
H₂S/CO₂, drilling channels and events. Planned outputs are PDF/DOCX/XLSX/CSV/TSV/HTML with
preview and preflight. Automatic rock-description fallback is not allowed.
