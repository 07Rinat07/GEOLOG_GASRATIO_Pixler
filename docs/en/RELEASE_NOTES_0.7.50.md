# GEOLOG GASRATIO@Pixler 0.7.50 — safe form switching

Fixed the critical PySide6 `Internal C++ object (CurveHeaderEditor) already deleted` failure that
could occur after editing a scale and switching the active working form.

## Changes

- `CurveHeaderEditor.dispose()` stops deferred range commits before widget deletion;
- minimum/maximum, unit, scale, and action controls block signals during disposal;
- `TabletTrackWidget` quiesces editors and event filters before `deleteLater`;
- `TabletView` has a rebuild guard that prevents nested layout reconstruction;
- MainWindow ignores stale header events during a form transaction;
- rollback rebuilds from a fresh deep copy of the model and never reuses old Qt objects;
- Form Manager no longer performs two restorations for one failed apply;
- cancelling after preview restores the original form separately and exactly once.

## Compatibility

Package **0.7.50**; project format **v20**; form schema **v6**; tablet layout **v16**.
No migration is required.

## Verification

Focused lifecycle/form/layout: **171 passed**. Available headless regression:
**1044 passed, 4 skipped, 4 deselected**. `compileall` passed. Final Qt lifecycle verification
requires a Windows/PySide6 smoke test.
