# Current project status

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
