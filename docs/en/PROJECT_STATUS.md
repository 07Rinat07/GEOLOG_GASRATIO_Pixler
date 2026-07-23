# Project status

23 July 2026 test build: package **0.7.45**, project format **v20**.

Completed: axis-independent tablet grid overlay; per-column grid/tick controls; editable curve-header scale and colours; reusable form revision/viewport persistence; 19 transparent tightly cropped symbols; explicit safe daily append to one DEPTH/TIME dataset; idempotent SHA-256 imports; per-dataset append history; default new depth LAS step 0.2 m.

Before stable: Windows/HiDPI visual smoke test, real daily LAS trial, full Qt/LAS/Ruff/mypy gate and physical-print verification. Directory watching and multi-dataset overlay within one form remain separate future slices.


## Slice verification

Focused forms/grid/symbols/daily-LAS/project/codec suite: **146 passed**. Available headless regression: **995 passed, 4 skipped, 3 deselected**. `compileall` passed; wheel 0.7.45 built successfully and contains all 19 transparent-symbol assets.

Next slice: read-only offline WITSML 2.1 inventory and mapping fixtures.
