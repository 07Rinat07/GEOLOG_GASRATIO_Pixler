# Project status

24 July 2026: package **0.7.60**, project format **v20**, form schema **v6**, tablet layout **v16**.

## Completed in 0.7.60

- replaced the native floating statistics window with an in-tablet overlay;
- the panel no longer consumes form width and cannot leave the workspace;
- a user-selected position survives main-window resizing;
- closing the panel or switching form/dataset clears interval analysis;
- panel actions adapt to narrow widths;
- added pure geometry, source-contract, and Qt regression tests;
- removed hotfix details and test results from the root README;
- added an automated root-README scope test.

## Verification

Container verification: **19 focused passed**; available headless regression:
**1094 passed, 4 skipped, 3 deselected**. Qt tests require Windows/PySide6.

## Next vertical slice

Read-only offline WITSML 2.1 inventory and mapping fixtures.
