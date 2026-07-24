# Project plan

Current as of 24 July 2026. Hotfix 0.7.50 keeps project format v20, form schema v6, and tablet
layout v16. After Windows confirmation, the next product slice is read-only offline WITSML 2.1
inventory and mapping fixtures.

## P0 — hotfix 0.7.50: safe form-widget lifecycle

- [x] stop header debounce timers before deleting the old Qt tree;
- [x] block minimum, maximum, unit, and scale signals during disposal;
- [x] remove track event filters before `deleteLater`;
- [x] ignore header mutations during a layout transaction/rebuild;
- [x] restore only from a deep-copied `TabletLayout`, with no widget references in snapshots;
- [x] use one original rollback snapshot for the accepted form;
- [x] remove the second Form Manager rollback after reversible apply;
- [x] retain a separate original-form rollback when preview is cancelled;
- [x] cover disposal, single rollback, and rebuild guards with headless tests;
- [ ] run a Windows/PySide6 smoke test with 20 consecutive switches between wide and narrow
  forms, including a minimum/maximum edit immediately before switching.

0.7.50 exit criterion: repeated switching never raises `Internal C++ object already deleted`;
any failure leaves a complete working previous form rather than a partially rendered tablet.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation for daily growth;
- [ ] secured ETP 1.2 only after successful fixture replay.
