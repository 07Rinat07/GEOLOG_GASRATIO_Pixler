# Project status

Snapshot: 23 July 2026. Version 0.7.28, test build.

## Release decision

The automated release gate is green: Ruff passes, mypy reports zero errors across 257 source
files, and the complete pytest run reports 1,188 passed and 10 skipped without a Qt/Python
process abort. The build remains a test build until the Windows, HiDPI, PDF, and physical
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

The annotation event router and pan/zoom/keyboard navigation are now isolated from
`TabletView` behind headless tests. Next checkpoint: sign off the Windows smoke matrix,
then extract track lifecycle. See the [audit](PRODUCT_AUDIT_2026.md) and
[plan](PROJECT_PLAN.md).
