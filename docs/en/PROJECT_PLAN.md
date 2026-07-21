# Project plan

Date: 21 July 2026

1. **GeoData Depth Workspace** — complete the reference-aligned daily screen, unified creation and
   re-editing of lithology, cuttings, LBA, calcimetry, and text, adaptive layout, and persistence.
   Absolute and relative gas-component composition is implemented.
2. **Masterlog** — unify header and body designers and use one template for preview, PDF, and the
   physical printer.
3. **Gas Ratio & Pixler** — separate scales, controlled interpretation rules, markers, and an
   explanation of each result.
4. **Release verification** — real LAS files, Windows screen matrix, physical printing, migrations,
   and synchronized RU/KK/EN documentation.

Completed items are listed in [Project status](PROJECT_STATUS.md) and the
[Depth workspace guide](GEODATA_DEPTH_WORKSPACE.md).

5. **Captions and stratigraphy** — keep the full track editor, project catalog, interval input, and
   persistence as a mandatory part of every production form.

## LAS Editor 2

- [x] ascending copy without modifying the original;
- [x] progressive merge with metadata preservation;
- [x] external LAS curve insertion with depth mapping;
- [x] pencil editing and synchronous recalculation;
- [x] batch table operations and exports.

### Next pencil verification

Run a Windows smoke test on a real LAS file: parameter selection, drawing in both directions, Undo/Redo, dependent-curve recalculation, project saving and updated LAS export. After stabilization, add direct drawing inside the multi-track tablet.

## Universal Constructor 0.7.0

The application now includes the `Ctrl+Shift+K` Constructor, 117 lithotypes, 19 symbols, a
physical-page-aware WYSIWYG header canvas, A0–A4/Letter/Legal/custom/roll profiles, broad
image import, semantic depth symbols with X/Y offsets, automatic/manual legends, preview and
preflight. Next: Windows smoke testing, rulers/guides/Undo and an explicit screen-to-print
profile link. See [Constructor plan](FORM_CONSTRUCTOR_PLAN.md).
