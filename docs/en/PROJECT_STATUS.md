# Project status

24 July 2026 corrective test build: package **0.7.49**, project format **v20**, form schema
**v6**, tablet layout **v16**.

## Completed in 0.7.49

- new and automatically materialized curves default to a linear scale;
- manual minimum/maximum are included in the render key and rebuild normalized curve geometry;
- ranges apply after a short debounce or immediately with Enter;
- the responsive header preserves minimum, maximum, unit, and scale type in narrow columns;
- the engineering ruler keeps the column's exact major/minor grid divisions;
- a candidate form renders before it is committed to the session;
- render/commit failure restores the last working form, dirty state, and selected track;
- cancelling Form Manager after preview restores the original configuration;
- explicitly persisted logarithmic bindings remain unchanged;
- project/form/layout schemas are unchanged and require no migration.

Verification: focused **150 passed**; available headless regression **1037 passed, 4 skipped, 3 deselected**; `compileall`
and wheel build passed. Windows Qt/HiDPI, narrow-column, and rollback smoke tests remain required
because PySide6/pyqtgraph are unavailable in the container.

Next slice: read-only offline WITSML 2.1 inventory and mapping fixtures.
