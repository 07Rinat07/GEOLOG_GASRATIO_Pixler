# Project status

Snapshot: 23 July 2026. Version 0.7.30, test build.

## Release decision

The last complete 0.7.28 baseline is green: Ruff passes, mypy reports zero errors across
262 source files, and the full pytest run reports 1,217 passed and 10 skipped. For 0.7.30,
`compileall`, wheel packaging, and 73 headless/regression/source-integrity tests covering
session binding, workspace commands, project controllers, and the print boundary completed
successfully. The full gate must be repeated in an installed environment because this container
lacks PySide6, pyqtgraph, lasio, Ruff, and mypy, while the available package index does not
provide them. The build remains a test build until that gate and the
Windows/HiDPI/PDF/physical-printer matrix pass.

## Working foundation

- safe LAS, CSV, TXT, Excel, and Paradox import/edit workflows;
- multi-dataset and multi-index projects;
- multi-track tablet, intervals, lithology, and forms;
- Masterlog, PDF, Print Center, and configurable major/minor grids;
- `Shift + left drag` interval statistics and XLSX/CSV export;
- annotations, project assets, and legacy migrations;
- synchronized RU/KK/EN user documentation.

Print execution now goes through `PrintJobExecutor`. `SessionBindingController` rebinds 26
controllers and clears their Undo/Redo or transient selection state. Project-tree actions go
through `WorkspaceCommandController`, so the tree handler in `MainWindow` no longer writes
`current_well_id/current_dataset_id` directly. The next slice prevents direct mutation of the
serializable project model from UI classes.

See the [audit](PRODUCT_AUDIT_2026.md) and [plan](PROJECT_PLAN.md).
