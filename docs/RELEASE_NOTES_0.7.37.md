# Примечания к выпуску 0.7.37 — единая coverage-модель

## Основное

- добавлен Qt-независимый `services/coverage.py`;
- явно разделены `observed_value`, `observed_zero`, `missing_sample` и
  `channel_unavailable`;
- `ReportDefinition` повышена до schema v2 и поддерживает ожидаемые
  `channel_mnemonics` на уровне отчёта и section;
- payload definition schema v1 мигрируется в runtime schema v2;
- `ResolvedReportDefinition` содержит доступные curve IDs, недоступные мнемоники и coverage
  фактического интервала;
- `Report Passport` повышен до schema v2 и подписывает coverage snapshot;
- интервальная статистика показывает availability, observed, zeros, missing и coverage;
- CSV/TSV различает `0`, пустой missing sample и `#N/A` для unavailable channel;
- XLSX публикует те же значения и расширенные coverage-метаданные на листе `Parameters`;
- JSON и Parquet включают структурированный coverage payload для каждой кривой;
- Curve Catalog использует общий coverage analyzer;
- формат проекта остаётся v16.

## Проверки

Wheel 0.7.37 успешно собран без build isolation; metadata и наличие нового coverage-модуля проверены.

Целевой coverage/report/export набор: 57 passed, 1 optional Parquet scenario skipped. Доступная регрессия: 876 passed, 4 skipped, 3 LAS tests deselected; полный Ruff/mypy/Qt/LAS gate и ручной
Windows/HiDPI/PDF/physical-print smoke-test остаются обязательными перед stable.
