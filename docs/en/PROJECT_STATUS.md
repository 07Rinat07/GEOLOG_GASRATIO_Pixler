# Project status

24 July 2026 corrective build: package **0.7.55**, project format **v20**, form schema **v6**, tablet layout **v16**.

## Completed in 0.7.55

- retained one common header band for exact depth-plot origin alignment;
- packed every track's parameter rows contiguously from the top;
- routed surplus synchronized height into one trailing stretch below the final row;
- retained scrolling for dense tracks that exceed the header cap;
- removed the constructor `opened_from_projection` NameError;
- added Qt and static regression contracts for top-packed headers.

## Verification

Focused header/form/constructor suite: **86 passed**. Available headless regression: **1064 passed, 4 skipped, 4 deselected**. `compileall` passed. A Windows/PySide6 visual smoke test remains required across different forms and DPI values.

## Next vertical slice

Read-only offline WITSML 2.1 inventory and mapping fixtures.
