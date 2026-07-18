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
- cache metrics and 100k/1M/5M benchmark scenarios.

Remaining:

- static-layer cache;
- explicit invalidation by data/style/layout revision;
- dirty-track and overlay repaint;
- performance diagnostics and accepted budgets on real LAS files.

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
