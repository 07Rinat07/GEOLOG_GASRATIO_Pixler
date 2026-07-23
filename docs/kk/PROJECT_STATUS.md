# Жоба мәртебесі

Кесім: 2026 жылғы 23 шілде. Нұсқа: 0.7.39, тесттік жинақ.

## Орындалды

- recoverable report-output transaction schema v1;
- staging, journal, backup, install, rollback және recovery;
- дайын output fingerprints бар Report Passport schema v4;
- sidecar load кезінде PDF/image/CSV/XLSX өзгерісін анықтау;
- артық continuation pages транзакциялық тазалау;
- Print Center, direct PNG/SVG/PDF, CSV/XLSX, Masterlog және interpretation PDF үшін ортақ service;
- manual recovery tool;
- project format v16 болып қалады.

Тексеру: 37 focused tests; қолжетімді regression — 915 passed, 4 skipped,
3 LAS tests deselected. Толық Qt/LAS/Ruff/mypy gate, Windows/NTFS/network-share recovery,
PDF/HiDPI және physical-print smoke-test міндетті.

Келесі кезең: ReportDefinition, Coverage, output transaction және Report Passport schema v4
арқылы DOCX және HTML adapters.

[Output транзакциясы](REPORT_OUTPUT_TRANSACTION.md) және [жалпы мәртебе](../PROJECT_STATUS.md).
