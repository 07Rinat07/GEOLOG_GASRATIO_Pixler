# Project status

Snapshot: 23 July 2026. Version 0.7.28, test build.

## Release decision

The automated release gate is green: Ruff passes, mypy reports zero errors across 258 source
files, and the complete pytest run reports 1,193 passed and 10 skipped with exit code zero.
The build remains a test build until the Windows, HiDPI, PDF, and physical
printer smoke matrix is signed off.

## Working foundation

- safe LAS, CSV, TXT, Excel, and Paradox import/edit workflows;
- multi-dataset and multi-index projects;
- multi-track tablet, intervals, lithology, and forms;
- Masterlog, PDF, Print Center, and configurable major/minor grids;
- `Shift + left drag` interval selection, all-visible-parameter statistics, and XLSX/CSV export;
- annotations, project assets, and legacy project migrations;
- synchronized RU/KK/EN user documentation.

Annotation hit routing has been restored, Windows SVG locking and PySide6 PNG-buffer
compatibility have been fixed, and the tablet toolbars now adapt to narrow screens.

The annotation event router, navigation, and track order/reuse are now isolated from
`TabletView`. Reorder and Undo/Redo preserve existing chart instances. Next checkpoint:
sign off the Windows smoke matrix, then extract track creation/disposal. See the
[audit](PRODUCT_AUDIT_2026.md) and
[plan](PROJECT_PLAN.md).
