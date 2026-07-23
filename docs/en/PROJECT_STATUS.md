# Project status

Snapshot: 23 July 2026. Version: 0.7.39, test build.

## Completed

- recoverable report-output transaction schema v1;
- staging, journal, backup, install, rollback, and recovery;
- Report Passport schema v4 with completed-output fingerprints;
- PDF/image/CSV/XLSX tamper detection when loading a sidecar;
- transactional cleanup of obsolete continuation pages;
- one service for Print Center, direct PNG/SVG/PDF, CSV/XLSX, Masterlog, and interpretation PDF;
- manual recovery tool;
- project format remains v16.

Checks: 37 focused tests; available regression: 915 passed, 4 skipped, and 3 LAS tests
deselected. The full Qt/LAS/Ruff/mypy gate plus Windows/NTFS/network-share recovery,
PDF/HiDPI, and physical-print smoke tests remain mandatory.

Next slice: DOCX and HTML adapters through ReportDefinition, Coverage, output transaction, and
Report Passport schema v4.

See [Report output transaction](REPORT_OUTPUT_TRANSACTION.md) and the [engineering status](../PROJECT_STATUS.md).
