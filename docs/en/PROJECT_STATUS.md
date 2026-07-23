# Project status

Snapshot: 23 July 2026. Version 0.7.31, test build.

## Release decision

The last complete 0.7.28 baseline is green: Ruff passes, mypy reports zero errors across
262 source files, and the full pytest run reports 1,217 passed and 10 skipped. For 0.7.31,
`compileall`, wheel packaging, and the available headless regression completed with 714 passed
and 4 platform-specific skips. Full pytest collection stops at 95 Qt/LAS-dependent modules
because this container lacks PySide6, pyqtgraph, and lasio; Ruff and mypy are unavailable as
well. The build remains a test build until the full gate and the Windows/HiDPI/PDF/physical-
printer matrix pass.

## Working foundation

- safe LAS, CSV, TXT, Excel, and Paradox import/edit workflows;
- multi-dataset and multi-index projects;
- multi-track tablet, intervals, lithology, and forms;
- Masterlog, PDF, Print Center, and configurable major/minor grids;
- `Shift + left drag` interval statistics and XLSX/CSV export;
- annotations, project assets, and legacy migrations;
- synchronized RU/KK/EN user documentation.

State-changing UI actions now cross controller/service boundaries. Tablet resize/reorder,
vertical-index, and visible-range changes use a dedicated headless mutation boundary;
`MainWindow` no longer writes serialized collections or `dirty` directly. A cancelled merge or
external-LAS export transaction removes the temporary dataset and restores the previous selection
and dirty state. `SessionBindingController` now rebinds 27 controllers.

The next slice is the Semantic Channel Dictionary followed by one Import Review.

See the [audit](PRODUCT_AUDIT_2026.md) and [plan](PROJECT_PLAN.md).
