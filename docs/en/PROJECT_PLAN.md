# Project plan

Current as of 24 July 2026. Hotfix **0.7.52** keeps project format v20, form schema v6 and tablet
layout v16. The next domain slice after Windows validation is read-only offline WITSML 2.1
inventory and mapping fixtures.

## P0 — hotfix 0.7.52: idempotent Qt teardown and compact headers

- [x] validate QObject wrappers with `shiboken6.isValid()`;
- [x] remove event filters and schedule deletion safely;
- [x] continue disposing remaining tracks after one wrapper failure;
- [x] make repeated tablet reset idempotent;
- [x] prevent dead `CurveHeaderEditor` objects from blocking import recovery or rollback;
- [x] reduce editable headers to 52 px and ordinary labels to 38 px;
- [x] retain direct min/unit/max editing and linear/log selection;
- [x] align the ruler with saved grid divisions and cap the common band at 360 px;
- [x] provide specific LAS duplicate/irregular-step/gap guidance;
- [x] cover cleanup, header and diagnostics contracts with headless tests;
- [ ] Windows/PySide6: reported LAS, 20 form switches, 20 resets and 100/125/150% DPI checks.

Exit criterion: imported data remains reachable, teardown never fails on deleted widgets, and the
working header is materially denser without losing scale or unit information.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation for daily growth;
- [ ] secured ETP 1.2 only after successful fixture replay.
