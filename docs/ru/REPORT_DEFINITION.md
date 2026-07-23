# Единая ReportDefinition

`ReportDefinition` schema v2 — неизменяемое описание одного отчёта. Оно фиксирует dataset,
точный индекс, разделы, stable curve IDs, ожидаемые мнемоники, форму, язык и режим интервала до
запуска preview или экспорта.

Resolver один раз формирует включительный набор строк, разрешает мнемоники, сохраняет
ненайденные каналы как unavailable и рассчитывает coverage. Preview, PDF/печать и CSV/XLSX не
вычисляют интервал или доступность повторно.

Payload schema v1 мигрируется в runtime schema v2. Project format v17 хранит
`well.operational_events`. Разделы `EVENTS` и `DRILLING` используют точные границы готового
`ResolvedReportDefinition`: depth → `depth_m`, relative time → `elapsed_time_s`, datetime →
UTC `measured_at`. Option `event_kinds` ограничивает типы событий без повторного resolve.

Подробнее: [общий контракт](../REPORT_DEFINITION.md) и [coverage-модель](COVERAGE_MODEL.md).
