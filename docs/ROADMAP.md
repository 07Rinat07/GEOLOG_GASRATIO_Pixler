# Roadmap — GEOLOG Gas Ratio & Pixler

## Current

### Tablet Engine 2.0 — Rendering Engine

Completed:

- shared depth/time camera and viewport;
- vertical and horizontal navigation;
- pinned depth track and minimap;
- peak-preserving LOD;
- LRU curve-geometry cache;
- unchanged-curve redraw suppression;
- static title/grid/axis descriptor cache;
- explicit dirty invalidation for data, style, viewport, static state and layout;
- partial single-track refresh without rebuilding adjacent tracks;
- independent cursor, selection, marker, annotation, preview, tooltip and rubber-band layers;
- per-layer visibility, Z-order and dirty revisions;
- overlay-only updates without curve-geometry rebuilds;
- cache and full/partial refresh metrics;
- 100k/1M/5M benchmark scenarios.

Remaining:

- performance diagnostics panel;
- accepted performance budgets on real Windows LAS files.

## Next

### Selection & Interaction Engine

- common hit-testing and selection;
- column drag-and-drop and resize handles;
- contextual editing and property panel;
- form-level Undo/Redo.

### Form Engine

- editable depth and time forms;
- arbitrary columns and curves;
- saved order, width, scale and style;
- custom parameters and mnemonic mapping;
- factory templates and user copies.

## Later, already agreed

- Normalized Gas;
- Gas Ratio;
- Pixler;
- hydrocarbon interpretation zones;
- printable graphical and textual interpretation reports.


- [x] Selection & Interaction Engine: базовая модель `HitResult`, `SelectionManager`, интеграция дорожек и интервалов, инфраструктура Undo/Redo.
- [ ] Selection & Interaction Engine: hit-testing кривых/заголовков, resize handles, drag-and-drop и панель свойств.
