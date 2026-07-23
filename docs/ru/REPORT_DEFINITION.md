# Единая ReportDefinition

`ReportDefinition` schema v2 — неизменяемое описание одного отчёта. Оно фиксирует dataset,
точный индекс, разделы, stable curve IDs, ожидаемые мнемоники, форму, язык и режим интервала до
запуска preview или экспорта.

Resolver один раз формирует включительный набор строк, разрешает мнемоники, сохраняет
ненайденные каналы как unavailable и рассчитывает coverage. Preview, PDF/печать и CSV/XLSX не
вычисляют интервал или доступность повторно.

Payload schema v1 мигрируется в runtime schema v2. Формат проекта остаётся v16.

Подробнее: [общий контракт](../REPORT_DEFINITION.md) и [coverage-модель](COVERAGE_MODEL.md).
