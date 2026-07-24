# Project status

24 July 2026 corrective build: package **0.7.58**, project format **v20**, form schema **v6**, tablet layout **v16**.

## Completed in 0.7.58

- fixed partial clipping of the final parameter in dense curve-header columns;
- the header viewport is snapped to complete 58 px parameter rows;
- header content keeps a bottom safety clearance so the last border cannot disappear below the plot;
- columns with more than six parameters expose clear row-based vertical scrolling;
- added a restrained screen-only curve colour profile without changing persisted colours or print output;
- ordinary thin pens become lighter in multi-curve tracks;
- major/minor grids are more neutral and minor lines are hidden when their pixel spacing is unreadable;
- removed obsolete duplicate UI import controllers and retained the services-layer import workflow;
- preserved interval-statistics overlay, A4 form audit, and runtime diagnostics.

## Verification

Focused header/screen-style/source-contract: **19 passed**. Available headless regression: **1070 passed, 4 skipped**. `compileall` passed. Windows/PySide6 smoke testing is still required for 7–12 row headers, wheel scrolling over headers, and grid comparison at 80/160/300 px track widths.

## Next vertical slice

Read-only offline WITSML 2.1 inventory and mapping fixtures.
