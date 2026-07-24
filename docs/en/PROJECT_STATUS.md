# Project status

24 July 2026 corrective build: package **0.7.56**, project format **v20**, form schema **v6**, tablet layout **v16**.

## Completed in 0.7.56

- added one A4 form-width audit for portrait and landscape orientation;
- Form Library reports physical/logical width, fit percentage, and an actionable recommendation;
- the structure editor refreshes the warning while column widths change;
- editor preview marks portrait and landscape A4 boundaries;
- the tablet status bar continuously reports the current form-width class;
- interval statistics automatically dock right or bottom and remain inside the screen;
- diagnostics include form width and A4 percentages.

## Verification

Focused width/layout/source-contract: **13 passed**. Available headless regression: **1069 passed, 4 skipped, 3 deselected**. `compileall` passed. Windows/PySide6 smoke testing remains required for dock transitions, window resizing, and 100/125/150% DPI.

## Next vertical slice

Read-only offline WITSML 2.1 inventory and mapping fixtures.
