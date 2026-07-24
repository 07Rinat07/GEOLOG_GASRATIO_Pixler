# Project status

24 July 2026 corrective test build: package **0.7.47**, project format **v20**, form schema
**v6**, tablet layout **v15**.

## Completed in 0.7.47

- mixed DB depth order is normalized in the accepted copy without changing the source;
- Import Review no longer blocks repairable `D1174.db`-class inputs;
- batch DB → LAS uses explicit DEPT/DEPTH/MD fields and saved manual profiles;
- weak ambiguous candidates still require confirmation;
- each ordinary curve header directly edits and persists minimum/maximum;
- automatic range, logarithmic validation, header-name color, and underline color use the existing
  `CurveDisplaySettings` contract without a project migration;
- the 0.7.46 import diagnostic center remains active.

Verification: **149 passed, 3 skipped, 3 deselected** in the focused suite and **1012 passed,
4 skipped, 3 deselected** in the available headless regression. `compileall` passed and wheel
0.7.47 built. A Windows DB/Qt smoke test remains mandatory.

Next slice: read-only offline WITSML 2.1 inventory and mapping fixtures.
