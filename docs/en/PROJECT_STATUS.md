# Project status

24 July 2026 corrective full build: package **0.7.58**, project format **v20**, form schema **v6**, tablet layout **v16**.

## Completed in 0.7.58

- rebuilt the change directly in the complete 0.7.56 project tree;
- interval statistics is always a floating overlay and no longer reduces tablet width;
- geometry is clamped to the active monitor, including multi-monitor coordinates;
- the overlay follows main-window move and resize events;
- window close, Clear, form switching, and dataset switching remove stale selection;
- previous A4 guidance, reusable forms, diagnostics, and all earlier fixes remain included;
- added three geometry tests and four integration contract tests.

## Verification

Focused overlay suite: **27 passed**. Available headless regression: **1048 passed, 4 skipped**. `compileall` completed for `src` and `tests`. A full visual smoke test requires Windows with PySide6/pyqtgraph.

## Next vertical slice

Read-only offline WITSML 2.1 inventory and mapping fixtures.
