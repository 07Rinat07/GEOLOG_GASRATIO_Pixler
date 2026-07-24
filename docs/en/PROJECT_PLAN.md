# Project plan

Current on 24 July 2026. Hotfix **0.7.58** keeps project format v20, form schema v6, and tablet layout v16.

## P0 — hotfix 0.7.58: complete header rows and readable screen plots

- [x] calculate header content and viewport geometry with pure functions;
- [x] cap the viewport at six complete rows without exposing a partial next row;
- [x] keep bottom clearance so the final parameter cannot slide under the plot;
- [x] scroll dense headers one row at a time with a visible scrollbar;
- [x] replace saturated hue-wheel fallback colours with a restrained palette;
- [x] reduce screen saturation without changing persisted colours or print output;
- [x] reduce only ordinary thin pens in multi-curve tracks;
- [x] soften minor grids and hide them when pixel spacing is unreadable;
- [x] synchronize README, status, testing, and RU/KK/EN release notes;
- [ ] Windows/PySide6: verify forms with 1, 6, 7, 9, and 12 parameters at 100/125/150% DPI.

Exit criterion: no parameter row is displayed partially, the final row is reachable through scrolling, and multi-curve plots remain readable without a neon palette or excessive minor grid.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation for daily growth;
- [ ] secured ETP 1.2 only after successful fixture replay.
