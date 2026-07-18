# Roadmap

## Product objective

Build a professional depth/time geological tablet where LAS import, canonical parameters, calculations, interpretation zones, and printable reports operate on one reproducible project model.

## P0 — Documentation and compatibility

- keep README files limited to the current product description and quick start;
- keep release history in CHANGELOG only;
- maintain synchronized RU/KK/EN user documentation;
- preserve project/layout migrations and back up user libraries.

## P1 — Tablet Engine 2.0 — current priority

### Completed navigation slice

- common `TabletCamera` for depth and time axes;
- cursor-anchored `Ctrl+wheel` zoom;
- bounded wheel scrolling;
- `Home`, `End`, `PageUp`, `PageDown`, `Up`, and `Down`;
- middle-button and `Space + left button` drag-scroll;
- synchronized visible window for every track;
- explicit vertical scrollbar and go-to value retained.

### Next slices

- true horizontal track viewport with pinned depth track;
- depth/time minimap and draggable visible-window handles;
- peak-preserving LOD/downsampling and viewport cache;
- repaint only dirty tracks and overlays;
- benchmarks at 100k, 1M, and 5M samples.

## P2 — Form Engine

- editable depth and time forms;
- unlimited columns and curves;
- drag-and-drop order, resizable widths, visibility, pinning;
- linear/log scales, independent axes, styles, grids, and headers;
- factory templates plus editable user copies;
- form schemas and migrations.

## P3 — Canonical parameter and mnemonic registry

- built-in Sensors catalog plus user rules;
- create/edit/delete canonical parameters and aliases;
- unit and physical-dimension validation;
- automatic mapping for future LAS imports;
- conflict explanation and provenance.

## P4 — Calculation Engine

- safe formulas and dependency graph;
- versioned methods, provenance, quality masks, and recalculation;
- cycle detection and unit validation.

## P5 — Normalized Gas Engine

- raw/normalized Total Gas and C1–C5;
- profiles using ROP, hole/bit diameter, mud flow, circulation state, lag, and optional extractor calibration;
- `K_NORM`, validity and quality curves;
- reproducible calculation metadata.

## P6 — Gas Ratio and Pixler

- original Pixler ratios as a separate versioned method;
- Wetness/Balance/Character and custom ratios as separate methods;
- raw or normalized source selection;
- classification zones and quality flags.

## P7 — Interpretation zones

- hydrocarbon candidate/verified intervals, markers, fills, labels, comments, confidence, and audit history;
- synchronized graph, table, properties, and text description.

## P8 — Automatic candidates

- explainable suggestions from background gas, normalized gas, C1–C5, ratios, Pixler, drilling state, trip/recycled-gas exclusions;
- specialist confirmation required.

## P9 — Print and report engine

- editable print headers;
- tablet plus interval table and textual interpretation;
- A4/A3/roll, PDF/SVG/PNG, selected intervals or full range.

## P10–P12

- LAS 1.2/2.0 and applicable LAS 3 sections; later WITSML 2.1 adapter;
- multi-well correlation workspace;
- acceptance/performance tests, recovery, backup, Windows installer, and 1.0 release.
