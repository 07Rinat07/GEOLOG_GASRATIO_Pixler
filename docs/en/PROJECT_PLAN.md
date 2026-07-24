# Project plan

Current as of 24 July 2026. Hotfix **0.7.55** keeps project format v20, form schema v6 and tablet layout v16.

## P0 — 0.7.55: top-packed curve headers

- [x] keep one shared header band so PlotWidget origins and depth grids remain aligned;
- [x] anchor every track's parameter stack to the top of that band;
- [x] consume all surplus height only below the final parameter;
- [x] stop sparse tracks from distributing blank space between curve scales;
- [x] retain vertical scrolling when a dense track exceeds the band limit;
- [x] repair the constructor `opened_from_projection` NameError;
- [x] cover the top-packed contract with Qt and source-level tests;
- [ ] Windows/PySide6: verify tracks with 1, 3 and 7+ curves at 100/125/150% DPI.

Exit criterion: parameter rows are contiguous from the top; any unavoidable remainder is below them, while all plots keep identical depth alignment.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation of daily growth;
- [ ] secured ETP 1.2 only after successful fixture replay.
