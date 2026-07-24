# Project status

24 July 2026 corrective build: package **0.7.52**. Project format **v20**, form schema **v6**,
tablet layout **v16**.

## Completed in 0.7.52

- fixed `Internal C++ object (CurveHeaderEditor) already deleted` during import recovery, tablet
  reset and form switching;
- validates every QObject wrapper with Shiboken before event-filter removal or `deleteLater()`;
- continues track disposal after one stale wrapper and makes repeated cleanup idempotent;
- reduced editable curve headers from 82 px to 52 px and ordinary labels to 38 px;
- preserved minimum, unit, maximum, scale type and engineering ruler in a compact layout;
- capped the synchronized header band at 360 px to reduce empty space;
- removed invalid QFont size and initial color-style warnings from diagnostics;
- kept duplicate indices, irregular steps and gaps as non-blocking LAS warnings with specific
  non-destructive actions.

## Verification

- focused lifecycle/header/diagnostics suite: **125 passed**;
- available headless regression: **1052 passed, 4 skipped, 4 deselected**;
- `compileall` passed;
- Windows/PySide6 smoke testing remains mandatory for the reported LAS, 20 form switches,
  repeated reset and narrow-column visual checks.

## Next vertical slice

Read-only offline WITSML 2.1 inventory and mapping fixtures. ETP 1.2 remains blocked until
fixture replay.
