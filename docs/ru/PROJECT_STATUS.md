# Статус проекта

Срез: 23 июля 2026 года. Версия: 0.7.39, тестовая сборка.

## Выполнено

- recoverable report-output transaction schema v1;
- staging, journal, backup, install, rollback и recovery;
- Report Passport schema v4 с fingerprint готовых output-файлов;
- проверка изменения PDF/image/CSV/XLSX при загрузке sidecar;
- транзакционная очистка устаревших страниц продолжения;
- общий сервис для Print Center, direct PNG/SVG/PDF, CSV/XLSX, Masterlog и interpretation PDF;
- ручной recovery tool;
- формат проекта остаётся v16.

Проверки: 37 целевых тестов; доступная регрессия — 915 passed, 4 skipped,
3 LAS tests deselected. Полный Qt/LAS/Ruff/mypy gate, Windows/NTFS/network-share recovery,
PDF/HiDPI и physical-print smoke-test остаются обязательными.

Следующий этап: DOCX и HTML adapters через ReportDefinition, Coverage, output transaction и
Report Passport schema v4.

См. [Filesystem-транзакция](REPORT_OUTPUT_TRANSACTION.md) и [общий статус](../PROJECT_STATUS.md).
