# Project plan

Current on 24 July 2026. Hotfix **0.7.56** keeps project format v20, form schema v6, and tablet layout v16.

## P0 — hotfix 0.7.56: A4 width guidance and adaptive statistics

- [x] calculate total visible form width in px and approximate mm;
- [x] compare the form with usable portrait and landscape A4 widths;
- [x] show fit percentages and recommendations in Form Library;
- [x] refresh guidance while columns are added, removed, or resized;
- [x] draw A4 boundaries in the structure-editor preview;
- [x] show a permanent A4 indicator in the tablet status bar;
- [x] move interval statistics from right dock to bottom dock on narrow windows;
- [x] prevent statistics from reopening as an off-screen floating window;
- [x] include form width and A4 class in diagnostics;
- [ ] Windows/PySide6: verify 1366×768, 1600×900, 1920×1080 and 100/125/150% DPI.

Exit criterion: before printing, the user can see whether the form fits portrait A4 and what to change; interval statistics remain fully reachable at every supported window size.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation for daily growth;
- [ ] secured ETP 1.2 only after successful fixture replay.
