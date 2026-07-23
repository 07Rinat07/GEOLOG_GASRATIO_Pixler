# Project status

Snapshot: 23 July 2026. Version: 0.7.38, test build.

## Completed

- one print-media schema v1 for A4/A3/custom/roll;
- Fit and 100% at reference DPI 96;
- vertical pages and horizontal continuations form one deterministic plan;
- preview, PDF, paged files, and the physical printer use one job;
- the system page range participates in the printer gate and final page count;
- the gate validates media, bounds, margins, printable area, DPI, and device state;
- Report Passport is now schema v3;
- project format remains v16.

Checks: 56 focused and 27 print-specific tests passed; available regression is
910 passed, 4 skipped, and 3 LAS tests deselected. The full Qt/LAS/Ruff/mypy gate and a real
Windows/HiDPI/PDF/physical-print smoke test remain mandatory.

Next slice: a recoverable output + passport filesystem transaction and output-file fingerprint.

See [Print media model](PRINT_MEDIA_MODEL.md) and the [engineering status](../PROJECT_STATUS.md).
