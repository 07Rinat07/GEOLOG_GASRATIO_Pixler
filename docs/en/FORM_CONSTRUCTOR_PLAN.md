# Universal form, header and print constructor

Updated: 21 July 2026  
Implementation version: 0.7.1

## Purpose

The **Constructor** menu is the unified entry point for tablet forms, printable Masterlog
forms, WYSIWYG headers, columns, page profiles, lithotypes, depth symbols, preview and
preflight. It reuses the existing Masterlog model and renderer instead of creating a second
incompatible print system.

## Implemented in 0.7.0

### Gate 0 — editor stabilization

- [x] Form Manager preview rebuilding is debounced and revision guarded;
- [x] stale previews are discarded during rapid form switching;
- [x] mouse wheel and touchpad navigation work over plots, headers and empty tablet areas;
- [x] wheel pans depth and `Ctrl + wheel` zooms around the pointer;
- [x] a visible navigation hint was added;
- [ ] run the mandatory Windows smoke test on real projects and common display sizes.

### Slice 23 — constructor asset catalog

- [x] processed the two lithotype archives and the symbol archive;
- [x] packaged 117 canonical lithotypes and 19 depth symbols;
- [x] preserved BMP sources, tiled rendering, thumbnails, checksums and aliases;
- [x] added RU/KK/EN names and normalized display names;
- [x] embedded resources inside the `geoworkbench` package;
- [x] resources are installed into the current project idempotently;
- [x] lithotypes are available to both tablet rendering and header legends.

### Slice 24 — in-application Constructor

- [x] added the top-level **Constructor** menu and `Ctrl+Shift+K` shortcut;
- [x] added tabs for tablet forms, print forms/headers, assets and preflight;
- [x] unified access to Form Manager, Masterlog templates, columns, mapping, page setup and preview;
- [x] added searchable thumbnail libraries with kind filters and multi-selection;
- [x] factory resources remain read-only while projects receive independent normalized assets.

### Slice 25 — WYSIWYG header designer

- [x] millimetre-based `QGraphicsScene/QGraphicsView` canvas;
- [x] A0–A4, Letter, Legal, custom and roll formats;
- [x] portrait and landscape orientation;
- [x] visible physical page boundary and red overflow region;
- [x] text, dynamic fields, images, lines, lithology legend and LBA legend;
- [x] BMP/PNG/JPEG/TIFF/WebP/SVG import;
- [x] fit/fill/stretch, rotation and opacity;
- [x] grid, snapping, mouse movement, duplication and ordering;
- [ ] rulers, arbitrary guides, grouping, layer locking and canvas-wide Undo/Redo.

### Slice 26 — symbols and dynamic legends

- [x] depth, interval, curve-parameter and time anchors;
- [x] column, parameter, image, size and label selection;
- [x] independent X/Y millimetre offsets while preserving the semantic anchor;
- [x] offsets are honored by preview, PDF and physical printing;
- [x] legend scopes: used, all, manually selected, and used plus selected;
- [x] new project lithotypes appear automatically and may be selected manually;
- [ ] automatic legend of used depth symbols;
- [ ] direct symbol dragging on print preview with offset persistence.

### Slice 27 — preview, printing and preflight

- [x] one Masterlog renderer for preview and output;
- [x] multipage depth and column-group rendering;
- [x] preflight checks datasets, columns, header overflow, missing assets, bindings and symbols;
- [x] preflight is available inside Constructor;
- [ ] overlap, minimum font-size and effective image-DPI checks;
- [ ] navigation from an issue to the affected canvas object;
- [ ] explicit serialized linkage between a tablet form and a print template.

## Next priority

1. Windows smoke-test Form Manager and depth navigation.
2. Add rulers, guides, locking and Undo/Redo.
3. Add direct preview dragging for symbols.
4. Add symbol legends and expanded preflight.
5. Link screen and print templates through an explicit profile ID.

## Constructor-related 0.7.1 slice

- [x] 0°/±90° and top/centre/bottom for stratigraphy intervals;
- [x] the same properties for screen-form column and track captions;
- [x] the same properties for WYSIWYG text, fields, and lithotype swatches;
- [x] all 117 standard BMP lithotypes are immediately available in lithology and cuttings;
- [x] real thumbnails, project overrides, and factory reset;
- [x] one catalog drives `lithotype_swatch`, dynamic legends, preflight, and printing;
- [ ] Windows smoke-test for rotated labels and physical BMP-pattern printing.

## Implemented in 0.7.2

- stable base-rock IDs are mapped to the exact BMP patterns from both legacy catalogs;
- old pattern keys remain compatible;
- the screen renderer preserves native texture size at every zoom level;
- lithology/cuttings labels are off by default and controlled by the form.
