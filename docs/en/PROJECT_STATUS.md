# Project status

24 July 2026 corrective build: package **0.7.50**, a critical form-widget lifecycle fix.
Project format: **v20**, form schema: **v6**, tablet layout: **v16**.

## Completed in 0.7.50

- `CurveHeaderEditor` now has an explicit idempotent disposal contract;
- the range debounce timer is stopped before `deleteLater`, and editor signals are blocked;
- every track quiesces header callbacks and removes event filters before deleting its Qt tree;
- stale range/unit/scale events are ignored while the tablet layout is rebuilding;
- rollback creates a fresh Qt tree from `TabletLayout` and never reuses destroyed widgets;
- Form Manager passes the original snapshot into one reversible transaction and no longer runs
  a second competing rollback after a failed apply;
- cancelling preview still restores the original form, dirty state, and selected track;
- project/form/layout schemas are unchanged and require no migration.

## Verification

- focused form/layout/lifecycle suite: **171 passed**;
- available headless regression: **1044 passed, 4 skipped, 4 deselected**;
- `compileall` passed;
- a Windows PySide6 smoke test remains mandatory for rapid repeated form switching and
  confirmation that `Internal C++ object already deleted` no longer occurs.

## Next vertical slice

Read-only offline WITSML 2.1 inventory and mapping fixtures. ETP 1.2 remains blocked until
fixture replay.
