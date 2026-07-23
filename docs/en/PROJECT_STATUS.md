# Project status

Snapshot: 23 July 2026. Version: 0.7.37, test build.

## Completed

- shared coverage schema v1 distinguishes a real zero, a missing sample, and an unavailable channel;
- `ReportDefinition` schema v2 stores stable curve IDs and expected mnemonics;
- `ResolvedReportDefinition` exposes unavailable channels and interval-scoped coverage;
- CSV uses `0`, an empty cell, and `#N/A` respectively;
- XLSX, JSON, Parquet, interval statistics, Curve Catalog, and Report Passport use one coverage contract;
- Report Passport is now schema v2;
- project format remains v16.

Checks: 57 focused tests passed and 1 optional Parquet scenario skipped; available regression is
876 passed, 4 skipped, and 3 LAS tests deselected. The complete Qt/LAS/Ruff/mypy gate and Windows
printing smoke test remain mandatory.

Next slice: A4/A3/custom/roll, 100%/fit, page continuation, and the physical printer gate.

See [Coverage model](COVERAGE_MODEL.md), [ReportDefinition](REPORT_DEFINITION.md), and the
[engineering status](../PROJECT_STATUS.md).
