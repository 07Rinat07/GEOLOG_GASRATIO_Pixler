# Project status

Snapshot: 23 July 2026. Version: 0.7.40, test build.

## Completed

- shared `ReportDocumentModel` schema v1;
- DOCX and self-contained HTML from one `ResolvedReportDefinition`;
- exact row indices with no second interval calculation;
- Coverage: observed `0`, missing `—`, unavailable `#N/A`;
- deterministic OOXML with no macros or external embedded objects;
- inline-CSS HTML with no scripts or network resources;
- recoverable output transaction and Report Passport schema v4;
- fingerprints of the completed DOCX/HTML bytes;
- project format remains v16.

Checks: 73 passed focused tests; available regression: 926 passed, 4 skipped, 3 LAS scenarios deselected.
The full Qt/LAS/Ruff/mypy gate and Windows Word/browser/PDF/HiDPI/physical-print smoke tests
remain mandatory.

Next slice: typed drilling, gas, show, sample, casing, and formation-top events.

See [DOCX and HTML](DOCX_HTML_EXPORT.md) and the [engineering status](../PROJECT_STATUS.md).
