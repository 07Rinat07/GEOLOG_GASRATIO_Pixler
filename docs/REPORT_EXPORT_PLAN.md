# План подсистемы отчётов и интервального экспорта

Локализованные требования:

- [Русский](ru/REPORT_EXPORT.md)
- [Қазақша](kk/REPORT_EXPORT.md)
- [English](en/REPORT_EXPORT.md)

## Инженерная модель

Действующие основные сущности:

- `ReportDefinition` schema v2 — immutable runtime-профиль dataset/index/sections/curves/form/language/interval;
- `ResolvedReportDefinition` — единственный разрешённый диапазон, строки и curve IDs для downstream adapters;
- `ReportSectionDefinition` — выбранный типизированный раздел и порядок;
- `IntervalBoundaryPolicy` — способ образования интервалов;
- `IntervalReportRow` — одна воспроизводимая интервальная строка;
- `NumericAggregationDefinition` — статистики числового канала;
- `ReportProvenance` — источники, формулы, версии, единицы и предупреждения;
- `ReportExportService` — следующий общий слой для PDF/DOCX/XLSX/HTML/CSV/TSV.

В 0.7.37 Print Center preview/output, Masterlog и selected CSV/XLSX разрешают один
`ReportDefinition` schema v2. Общая coverage-модель различает observed zero, missing sample и
unavailable channel; разделы и exporters получают одни и те же coverage snapshots.

Базовый PDF кальциметрии/ЛБА уже существует. Новый этап должен расширить его до общего
отчёта по геологии, газам и технологии, не создавая второй несовместимый источник данных.
Подробные критерии и порядок реализации приведены в локализованных документах.
