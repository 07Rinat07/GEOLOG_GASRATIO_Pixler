# Статус проекта

Срез: 23 июля 2026 года. Версия: 0.7.37, тестовая сборка.

## Выполнено

- единая coverage schema v1 различает реальный ноль, пропущенный отсчёт и недоступный канал;
- `ReportDefinition` schema v2 хранит curve IDs и ожидаемые мнемоники;
- `ResolvedReportDefinition` содержит unavailable channels и coverage фактического интервала;
- CSV: `0` / пустая ячейка / `#N/A`;
- XLSX, JSON, Parquet, интервальная статистика, Curve Catalog и Report Passport используют один coverage-контракт;
- Report Passport повышен до schema v2;
- формат проекта остаётся v16.

Проверки: 57 целевых тестов пройдено, 1 optional Parquet-сценарий пропущен; доступная регрессия —
876 passed, 4 skipped, 3 LAS tests deselected. Полный Qt/LAS/Ruff/mypy gate и Windows print
smoke-test остаются обязательными.

Следующий этап: A4/A3/custom/roll, 100%/fit, page continuation и physical printer gate.

См. [Coverage-модель](COVERAGE_MODEL.md), [ReportDefinition](REPORT_DEFINITION.md) и
[общий статус](../PROJECT_STATUS.md).
