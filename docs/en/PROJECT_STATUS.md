# Project status

Snapshot: 23 July 2026. Version 0.7.28, test build.

## Release decision

The release gate is red. The complete pytest run fails and eventually aborts in the Qt path;
the first isolated failure is the missing `TabletView._annotation_ancestor`. Ruff reports
6 errors and mypy reports 142 errors across 33 files. Stable status is blocked until these
are fixed and the Windows, HiDPI, PDF, and printer smoke matrix is signed off.

## Working foundation

- safe LAS, CSV, TXT, Excel, and Paradox import/edit workflows;
- multi-dataset and multi-index projects;
- multi-track tablet, intervals, lithology, and forms;
- Masterlog, PDF, Print Center, and configurable major/minor grids;
- `Shift + left drag` interval selection, all-visible-parameter statistics, and XLSX/CSV export;
- annotations, project assets, and legacy project migrations;
- synchronized RU/KK/EN user documentation.

The targeted 116 grid tests and 38 interval-statistics tests pass, but they do not replace
the complete gate.

Next checkpoint: zero Ruff/mypy/pytest errors, no Qt crash, and a signed Windows smoke test.
See the [audit](PRODUCT_AUDIT_2026.md) and [plan](PROJECT_PLAN.md).
