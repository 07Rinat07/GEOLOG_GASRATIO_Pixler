# Release notes 0.7.33 — interactive Import Review

Date: 23 July 2026. Status: test build.

## New

- one `ImportReviewDialog` now covers CSV/TXT, Excel, LAS, and GeoScape/Paradox;
- users can select the active index and correct its mnemonic, role, type, and UOM;
- an additional numeric NULL sentinel can be converted to `NaN` in the accepted copy only;
- every channel can be enabled/excluded and given manual canonical mnemonic/kind, quantity class, and UOM overrides;
- the automatic Semantic Channel Dictionary mapping can be restored per channel;
- preview reports NULLs, duplicates, gaps, order, unresolved channels, UOM conflicts, all-NULL channels, and duplicate canonical kinds;
- blocking errors disable acceptance while warnings remain visible;
- accepted manual decisions are recorded in semantic binding evidence and dataset parameters.

## Architecture and safety

- `ImportReviewController` owns initial plans, read-only preview, and validated commit;
- preview and commit operate on deep copies and never mutate the loader-owned dataset;
- `DatasetImportJobExecutor` invokes review before the project-session port;
- cancelling CSV/Excel/Paradox or an individual LAS creates no dataset/well and does not change `dirty`;
- LAS batch import opens one review per file;
- a UOM edit is a metadata correction, not an implicit value conversion;
- project format remains v16.

## Verification

- 731 available headless/regression/source-integrity tests passed;
- 4 platform scenarios were skipped;
- 3 LAS round-trip tests require `lasio`, and 1 Qt scenario requires `PySide6`;
- `compileall` completed successfully;
- the full Ruff, mypy, Qt/LAS pytest, and Windows GUI/HiDPI/PDF/physical-print smoke gates still require the complete environment.
