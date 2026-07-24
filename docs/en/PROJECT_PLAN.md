# Project plan

Current on 24 July 2026. Full build **0.7.58** keeps project format v20, form schema v6, and tablet layout v16.

## P0 — 0.7.58: interval statistics without window expansion

- [x] implement the change directly in the complete project tree, without requiring a patch workflow;
- [x] keep interval statistics as a floating overlay over the tablet;
- [x] exclude statistics width from the main-window minimum size;
- [x] clamp the overlay to the active monitor work area;
- [x] reposition it when the main window moves or resizes;
- [x] keep title bar, close control, table, and export buttons reachable;
- [x] closing the overlay clears interval shading and dataset selection;
- [x] form switching clears the previous report before replacing the widget tree;
- [x] dataset/project switching also clears the previous analysis;
- [x] cover geometry with headless tests and integration source-contract tests;
- [ ] Windows/PySide6: verify 1366×768, 1600×900, 1920×1080, dual monitors, and 100/125/150% DPI.

Exit criterion: the form retains all available width; statistics may overlap the right side of the plots but never leaves the monitor; no stale interval survives close or form switching.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation for daily growth;
- [ ] secured ETP 1.2 only after successful fixture replay.
