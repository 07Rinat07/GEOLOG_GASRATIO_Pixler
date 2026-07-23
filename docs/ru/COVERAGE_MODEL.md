# Единая coverage-модель

Версия 0.7.37 различает четыре состояния данных:

- `observed_value` — конечное ненулевое значение;
- `observed_zero` — реальный конечный ноль;
- `missing_sample` — канал существует, но отсчёт `NaN/Infinity`;
- `channel_unavailable` — запрошенный канал отсутствует в dataset.

`ReportDefinition` schema v2 принимает curve IDs и ожидаемые мнемоники. Resolver сохраняет
ненайденные мнемоники как unavailable и формирует coverage только по строкам разрешённого
интервала.

В CSV ноль записывается как `0`, пропуск — пустая ячейка, недоступный канал — `#N/A`. В XLSX
лист `Parameters` показывает availability, observed, zeros, missing и coverage. JSON, Parquet и
Report Passport schema v3 содержат структурированный coverage payload.

Формат проекта остаётся v16. Полный контракт: [COVERAGE_MODEL.md](../COVERAGE_MODEL.md).
