# Project status

Snapshot: 23 July 2026. Package version: **0.7.44**, test build. Project format: **v19**.

The last fully confirmed automated baseline is 0.7.28: Ruff clean, mypy with zero errors in 262
source files, and full pytest with 1,217 passed and 10 skipped. For 0.7.44 this container completed
`compileall`, 72 focused tests, and the available headless regression: 987 passed, 4 skipped, and
3 deselected. The full Qt/LAS/Ruff/mypy gate requires PySide6, pyqtgraph, lasio, Ruff, and mypy.
Windows/HiDPI/PDF/physical-print smoke tests remain mandatory before a stable release.

Version 0.7.44 completes immutable lag correction profiles and revisions, constant-time,
annular-volume/flow, pump-stroke, and manual control-point methods, one derived dataset per revision,
source/corrected depth axes, explicit repeated-time aggregation, provenance fingerprints, tamper
checks, optimistic revision guards, a Qt workflow, and migration `v18 → v19`.

The current base includes typed operational events, deterministic QC, append-only acquisition with
checkpoints/replay, versioned lag/depth projections, ReportDefinition v2, Coverage v1, Report
Passport v4, recoverable output transactions, and PDF/XLSX/CSV/TSV/DOCX/HTML adapters.

Next slice: read-only offline WITSML 2.1 inventory and mapping fixtures. A network ETP 1.2 client is
not introduced before fixture replay succeeds, and credentials must remain outside project JSON.
