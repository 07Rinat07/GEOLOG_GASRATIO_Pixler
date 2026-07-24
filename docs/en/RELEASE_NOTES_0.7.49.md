# GEOLOG GASRATIO@Pixler 0.7.49 — responsive curve scales and transactional form switching

## Fixes

- new and automatically materialized curves default to a linear scale;
- header minimum/maximum are part of the render key and immediately rebuild normalized curve X geometry;
- manual ranges apply automatically after a short debounce or immediately with Enter;
- minimum and maximum share available width and remain reachable in narrow columns;
- unit and linear/logarithmic selection use a separate responsive row;
- the engineering ruler keeps the exact major/minor divisions of its column;
- a candidate form is fully rendered before it is committed to the project session;
- render or commit failures restore the last working layout, dirty state, and selected track;
- cancelling Form Manager after preview restores the original working configuration;
- printing from Form Manager stops when the selected form cannot be applied safely.

## Compatibility

- package: **0.7.49**;
- project format: **v20**;
- form schema: **v6**;
- tablet layout: **v16**;
- no project migration is required;
- explicitly saved logarithmic curves remain logarithmic; the linear default applies only to new and automatically generated bindings.

## Verification

Verification: **150 focused passed**; available headless regression: **1037 passed, 4 skipped, 3 deselected**; `compileall` and wheel build passed. PySide6 and pyqtgraph are unavailable in the build environment, so narrow-column, HiDPI, and real rollback smoke tests remain required on Windows.
