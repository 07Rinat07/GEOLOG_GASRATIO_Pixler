# Project plan

Current as of 24 July 2026. Corrective slice 0.7.49 keeps project format v20, form schema v6,
and tablet layout v16. After Windows validation, the next domain slice is read-only offline
WITSML 2.1 inventory and mapping fixtures.

## P0 — hotfix 0.7.49: reliable scales and safe forms

- [x] default new and automatically materialized curves to a linear scale;
- [x] include scale/minimum/maximum in the render key so manual ranges move the curve itself;
- [x] apply valid ranges after a debounce or immediately with Enter;
- [x] preserve both range editors at the minimum supported track width;
- [x] place unit and linear/logarithmic selection in a separate responsive row;
- [x] keep the engineering ruler aligned with the column's major/minor grid divisions;
- [x] render a candidate form before committing it to the project session;
- [x] restore the last working form, dirty marker, and selection after failure;
- [x] roll back live preview when Form Manager is cancelled;
- [x] prevent printing a form that could not be applied safely;
- [x] cover render-before-commit, rollback, and range geometry with headless tests;
- [ ] run Windows/PySide6/HiDPI smoke tests for narrow columns, manual ranges, and rollback.

0.7.49 exit criterion: editing minimum/maximum visibly repositions the curve; both boundaries
remain reachable in a narrow column; failed form switching or cancelled preview never leaves a
partially applied layout.

## Next slices

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation for daily growth;
- [ ] secured ETP 1.2 only after successful fixture replay.
