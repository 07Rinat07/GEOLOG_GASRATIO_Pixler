# Project status

24 July 2026 corrective test build: package **0.7.48**, project format **v20**, form schema
**v6**, tablet layout **v16**.

## Completed in 0.7.48

- ordinary curve headers now contain an engineering ruler rather than faint range fields;
- minimum/maximum stay visible at the edges and intermediate labels align with the column grid;
- major/minor ruler divisions reuse the same saved grid contract as screen and print;
- linear and logarithmic labels use separate interpolation;
- both limits can be prepared and applied together with `✓` or Enter;
- display unit and scale type are editable directly in the header;
- unit overrides are presentation-only and do not convert samples;
- unit/range/scale/header colors persist in tablet layout and user forms;
- layout v15 migrates to v16 without changing legacy source-unit behavior;
- DB/LAS recovery and diagnostics from 0.7.46–0.7.47 remain active.

Verification: focused suite **152 passed, 3 skipped, 3 deselected**; available headless regression
**1020 passed, 4 skipped, 3 deselected**; `compileall` passed. Windows Qt/HiDPI smoke testing
remains mandatory.

Next slice: read-only offline WITSML 2.1 inventory and mapping fixtures.
