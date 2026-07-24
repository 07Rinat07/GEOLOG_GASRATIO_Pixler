# GEOLOG GASRATIO@Pixler 0.7.52 — idempotent Qt cleanup and compact log headers

This corrective build is based on the user diagnostics package from 24 July 2026.

## Qt lifecycle recovery

- Tablet teardown validates every QObject wrapper with `shiboken6.isValid()` before calling it.
- Event-filter removal and `deleteLater()` are best-effort and safe when the C++ object was already deleted.
- Track disposal continues in reverse order even if one stale wrapper raises an exception.
- Import recovery and form switching therefore cannot be blocked by a dead `CurveHeaderEditor`.
- Cleanup remains idempotent: a second reset clears Python registries without touching destroyed widgets.

## Compact professional headers

- Editable curve headers were reduced from an 82 px row budget to 52 px.
- The caption row contains the linear/log selector, auto-range and settings actions.
- Minimum, display unit and maximum share one compact row.
- The engineering ruler remains aligned with saved major/minor grid divisions.
- Non-editable curve labels use a 38 px compact row.
- The synchronized header band is capped at 360 px instead of 480 px, substantially reducing empty space in tracks with fewer curves.

## Import diagnostics

- Duplicate index values, non-uniform step and index gaps remain non-blocking warnings.
- Their suggested actions now distinguish duplicate policy, optional 0.2 m derived resampling and intentional missing intervals.
- The source LAS is never rewritten by those recommendations.

Package **0.7.52**; project format **v20**; form schema **v6**; tablet layout **v16**.
Verification: **125 focused passed**; **1052 headless passed, 4 skipped, 4 deselected**; `compileall` and wheel build passed. PySide6/pyqtgraph/lasio are unavailable in the container, so the reported Windows scenario remains mandatory.
