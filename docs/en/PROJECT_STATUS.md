# Project status

Snapshot: 23 July 2026. Version 0.7.29, test build.

## Release decision

The last complete 0.7.28 baseline is green: Ruff passes, mypy reports zero errors across
262 source files, and the full pytest run reports 1,217 passed and 10 skipped. For 0.7.29,
source compilation and an expanded regression suite for import jobs, adapters, and the
project-session boundary completed with 105 passed and 3 platform skips; the 0.7.29 wheel built successfully. The full gate must be repeated in an installed environment because this container lacks
PySide6, pyqtgraph, lasio, Ruff, and mypy, while the package index was unavailable. The build
remains a test build until that gate and the Windows/HiDPI/PDF/physical-printer matrix pass.

## Working foundation

- safe LAS, CSV, TXT, Excel, and Paradox import/edit workflows;
- multi-dataset and multi-index projects;
- multi-track tablet, intervals, lithology, and forms;
- Masterlog, PDF, Print Center, and configurable major/minor grids;
- `Shift + left drag` interval selection, visible-parameter statistics, and XLSX/CSV export;
- annotations, project assets, and legacy project migrations;
- synchronized RU/KK/EN user documentation.

`ImportJobController` and `DatasetImportJobExecutor` now live in `services/import_jobs.py`.
The shared boundary executes CSV/Excel plans, applies strict/compatible/manual LAS policy,
preserves the lossless source/import report, and registers Paradox datasets. `MainWindow` only
collects user choices and presents outcomes; rejected or failed files cannot create a partially
registered dataset. The next slice covers print jobs and session binding.

See the [audit](PRODUCT_AUDIT_2026.md) and [plan](PROJECT_PLAN.md).
