# Project plan

Current as of 24 July 2026. Hotfix **0.7.53** keeps project format v20, form schema v6 and
tablet layout v16.

## P0 — readable engineering scales, compact interval statistics and stale-plot guards

- [x] label the ruler in the header with unit and linear/log mode;
- [x] strengthen the baseline, ticks and endpoint/intermediate labels;
- [x] refresh the ruler caption after unit or scale edits;
- [x] reduce statistics summary/table/header fonts and row height;
- [x] show mnemonic and unit under long parameter names;
- [x] skip deleted PlotWidget wrappers during cursor, wheel and depth-range updates;
- [x] cover the contract with focused and headless regression tests;
- [ ] Windows/PySide6: verify 80–400 px tracks, 100/125/150% DPI and repeated form switches.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays;
- [ ] directory watcher with preview confirmation;
- [ ] secured ETP 1.2 after fixture replay.
