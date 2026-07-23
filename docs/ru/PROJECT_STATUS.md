# Статус проекта

Срез: 23 июля 2026 года. Версия: 0.7.40, тестовая сборка.

## Выполнено

- общая `ReportDocumentModel` schema v1;
- DOCX и автономный HTML из одного `ResolvedReportDefinition`;
- точные row indices без повторного вычисления интервала;
- Coverage: реальный `0`, missing `—`, unavailable `#N/A`;
- deterministic OOXML без макросов и внешних объектов;
- HTML с inline CSS без scripts и сетевых ресурсов;
- recoverable output transaction и Report Passport schema v4;
- fingerprint фактических DOCX/HTML байтов;
- формат проекта остаётся v16.

Проверки: 73 passed целевых; доступная регрессия — 926 passed, 4 skipped, 3 LAS-сценария deselected.
Полный Qt/LAS/Ruff/mypy gate и Windows Word/browser/PDF/HiDPI/physical-print smoke-test
остаются обязательными.

Следующий этап: типизированные drilling/gas/show/sample/casing/formation-top события.

См. [DOCX и HTML](DOCX_HTML_EXPORT.md) и [общий статус](../PROJECT_STATUS.md).
