# Примечания к выпуску 0.7.37 — coverage-модель

- добавлен единый headless-анализатор coverage;
- ноль, пропущенный отсчёт и отсутствующий канал больше не смешиваются;
- `ReportDefinition` и `Report Passport` используют schema v2;
- CSV: `0`, пустая ячейка и `#N/A`; XLSX дополнительно показывает coverage-статистику;
- JSON/Parquet и паспорт содержат структурированный coverage payload;
- старые definition payload v1 мигрируют, формат проекта остаётся v16.

Подробнее: [Coverage-модель](COVERAGE_MODEL.md).

Проверки / checks: 57 focused passed, 1 optional skipped; 876 passed, 4 skipped, 3 LAS tests deselected.
