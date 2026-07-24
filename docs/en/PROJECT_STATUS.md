# Project status

24 July 2026 corrective build: package **0.7.51**, persistent runtime diagnostics and a safe
pencil/form lifecycle. Project format: **v20**, form schema: **v6**, tablet layout: **v16**.

## Completed in 0.7.51

- the application writes rotating `geolog.log` and separate `geolog-crash.log` files;
- uncaught Python/thread exceptions, Qt messages and Qt event-handler failures are captured;
- form apply/rollback, full tablet render and curve-pencil commit use stable event codes and
  complete tracebacks;
- Help menu commands open the log folder, copy the path and build a diagnostics ZIP;
- diagnostics bundles exclude LAS values, datasets, forms and project assets;
- pencil commit refreshes only affected and recalculated curve tracks;
- automatic header ranges update in place without deleting current header editors;
- the tablet is no longer fully rebuilt after every stroke, preserving the form, widths and
  horizontal position;
- pencil mode, preview and stale track/curve targets are cleared before a full form rebuild;
- a candidate form is validated before pencil mode ends and widgets are replaced;
- apply/rollback failures are logged while rollback still rebuilds solely from the model.

## Verification

- focused logging/form/pencil/tablet suite: **245 passed**;
- available headless regression: **1048 passed, 4 skipped, 4 deselected**;
- `compileall` passed;
- Windows PySide6 smoke testing remains mandatory for real drawing, Undo/Redo, immediate form
  switching after a stroke and diagnostics-bundle creation.

## Next vertical slice

Read-only offline WITSML 2.1 inventory and mapping fixtures. ETP 1.2 remains blocked until
fixture replay.
