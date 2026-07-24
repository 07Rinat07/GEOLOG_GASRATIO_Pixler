# GEOLOG GASRATIO@Pixler 0.7.47 — DB import recovery and editable header ranges

Corrective test build dated 24 July 2026. Project format remains **v20**.

## GeoScape / Paradox DB

- a mixed `DEPT/DEPTH/MD` order is now a repairable condition rather than an unusable file;
- Import Review enables sorting of the **accepted copy** by the active index while leaving the
  source `.db` and loader-owned dataset untouched;
- all indexes and curves use one stable row permutation;
- duplicate depths and gaps remain warnings, while NULL index values and a constant index remain
  blocking errors;
- batch DB → LAS prefers explicit `DEPT`, `DEPTH`, `MD`, `HOLEDEPTH`, and `BITDEPTH` fields even
  when the table classification is mixed;
- weak or tied generic candidates still require a profile or manual confirmation;
- manual/saved profiles are honored and the export copy is normalized before LAS write and
  round-trip verification.

## Curve header range and style

- minimum and maximum are directly editable in every ordinary curve header;
- the `A` button restores automatic range;
- edits are committed through `TabletController` and persisted in the current working form;
- logarithmic scales reject a non-positive minimum;
- full curve settings now expose independent header-name and underline colors;
- project format, form schema v6, and tablet layout v15 are unchanged.

## Verification

- focused DB/import/form suite: **149 passed, 3 skipped, 3 deselected**;
- available headless regression: **1012 passed, 4 skipped, 3 deselected**;
- `compileall` passed and wheel 0.7.47 built without isolation;
- `PySide6`, `pyqtgraph`, and `lasio` are unavailable in the container, so Windows smoke tests
  with the real `D1174.db`, batch DB → LAS, and header editors remain mandatory.
