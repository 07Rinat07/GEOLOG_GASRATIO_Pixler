# GEOLOG GASRATIO@Pixler 0.7.51 — runtime diagnostics and safe pencil lifecycle

This corrective build adds persistent support diagnostics and removes the full tablet rebuild that
followed every curve-pencil stroke.

## Runtime diagnostics

- Rotating UTF-8 log files are written to the application data `logs` directory.
- Uncaught Python exceptions, worker-thread exceptions, Qt messages and exceptions escaping Qt
  event handlers are recorded with time, version, component, event code and traceback.
- Form apply/preview/rollback, tablet full render, pencil activation/commit and curve refresh events
  are recorded as stable structured event names.
- Help menu commands open the log folder, copy the current log path and build a diagnostics ZIP.
- The diagnostics ZIP contains logs and system/runtime metadata only; LAS values, datasets, forms
  and project assets are not copied.

## Pencil and form safety

- A successful pencil edit refreshes only tracks containing the edited or recalculated curves.
- Automatic header ranges are updated in place; existing `CurveHeaderEditor` widgets are not deleted after a stroke.
- The current form, column widths, horizontal position and unrelated curve widgets are preserved.
- Any operation that must rebuild the complete form first disables pencil mode and clears stale
  track/curve targets before deleting Qt widgets.
- A valid candidate form is built before pencil mode is ended; invalid forms do not disturb the
  active workspace.
- Form apply and rollback failures are written to the persistent log with complete traceback.

Package **0.7.51**; project format **v20**; form schema **v6**; tablet layout **v16**.

Verification in the available environment: **245 focused passed**; **1048 headless passed,
4 skipped, 4 deselected**; `compileall` passed. PySide6/pyqtgraph/lasio are unavailable in the
container, so Windows smoke testing remains required for real drawing and repeated form switching.
