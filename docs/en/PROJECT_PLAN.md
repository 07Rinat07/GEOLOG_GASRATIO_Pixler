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

## Stratigraphy text 0.7.1

- [x] 0°, 90° bottom-to-top, and 90° top-to-bottom directions;
- [x] near-top, centre (default), or near-bottom placement;
- [x] project persistence and restoration during re-editing;
- [x] consistent tablet, preview, PDF, and print rendering;
- [ ] visual Windows verification for narrow columns and short intervals.

## Slice 0.7.1 — text and lithotypes

- [x] 0°/±90° and top/centre/bottom for stratigraphy, forms, and headers;
- [x] one factory layer containing all 117 lithotypes;
- [x] thumbnail selection in lithology and cuttings;
- [x] individual swatch and dynamic legend in headers;
- [x] project add, override, and reset workflows;
- [ ] Windows smoke-test and physical printing.

## Slice 0.7.2 — exact legacy lithotype rendering

- [x] map the stable base-rock IDs to the original BMP files from both supplied catalogs;
- [x] keep old hatch keys readable without manual project migration;
- [x] tile each bitmap in device pixels so depth zoom never stretches the pattern;
- [x] use one renderer in lithology, cuttings, header legends, preview, PDF and print;
- [x] keep text over the pattern disabled by default with an explicit form-editor switch;
- [x] full regression run: `988 passed, 1 skipped`; Ruff and compileall pass.
