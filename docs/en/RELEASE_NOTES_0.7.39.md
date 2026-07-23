# Release notes 0.7.39 — report output transaction

- output and Report Passport now commit through one recoverable filesystem transaction;
- completed files record SHA-256, byte size, MIME type, and safe basename in Passport schema v4;
- incomplete commits roll back, while committed operations finish cleanup without reverting;
- obsolete continuation pages are removed transactionally during overwrite;
- Print Center, direct PNG/SVG/PDF, CSV/XLSX, Masterlog, and interpretation PDF use the shared service;
- added `tools/recover_report_transactions.py`;
- project format remains v16.

Checks: 37 focused tests; available regression: 915 passed, 4 skipped, 3 LAS tests deselected.
