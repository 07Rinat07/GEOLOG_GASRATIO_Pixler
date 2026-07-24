# Project plan

Current on 24 July 2026. Version **0.7.60** keeps project format v20, form schema v6, and tablet layout v16.

## P0 — 0.7.60: screen-safe interval statistics and README discipline

- [x] replace the floating `QDockWidget` with a child overlay inside the tablet;
- [x] prevent the panel from consuming form width;
- [x] constrain size and position to the workspace;
- [x] preserve user position during resize without snapping right;
- [x] clear selection, shading, and report on close, form switch, and dataset switch;
- [x] compact panel buttons for narrow widths;
- [x] add pure geometry, source-contract, and Qt regression tests;
- [x] remove release notes and technical results from the root README;
- [x] add an automated README scope test;
- [ ] Windows/PySide6: verify drag/resize/close/form-switch at 100%, 125%, and 150% DPI.

Exit criterion: the panel remains inside the tablet, does not shrink the form, does not snap right after manual movement, and is fully cleared on form switch.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation for daily growth;
- [ ] secured ETP 1.2 only after successful fixture replay.
