# GEOLOG GASRATIO@Pixler 0.7.52 — safe Qt cleanup and compact curve headers

This corrective build uses the user diagnostics package from 24 July 2026.

- QObject wrappers are checked with `shiboken6.isValid()` before event-filter removal or deletion.
- Track cleanup continues after one stale wrapper, making import recovery and form switching idempotent.
- A deleted `CurveHeaderEditor` no longer blocks the fallback workspace.
- Editable curve headers use a compact 52 px budget instead of 82 px; ordinary labels use 38 px.
- Caption/actions, minimum-unit-maximum and the engineering ruler are arranged in three dense rows.
- The synchronized header band is capped at 360 px instead of 480 px.
- Duplicate indices, non-uniform steps and gaps remain warnings with specific non-destructive guidance.

Package **0.7.52**; project format **v20**; form schema **v6**; tablet layout **v16**.
Verification: **125 focused passed**; **1052 headless passed, 4 skipped, 4 deselected**; `compileall` and wheel build passed. PySide6/pyqtgraph/lasio are unavailable in the container, so Windows validation remains mandatory.
