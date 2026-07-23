# Единая ReportDefinition

`ReportDefinition` — неизменяемое описание одного отчёта. Оно фиксирует dataset, точный индекс,
разделы, каналы, форму, язык и режим интервала до запуска preview или экспорта.

## Интервалы

- `full` — вся выбранная ось;
- `current` — viewport, зафиксированный при открытии Print Center;
- `custom` — введённые пользователем границы;
- `selection` — выделенный интервал, только если он относится к той же оси.

Resolver проверяет dataset/index, ограничивает диапазон фактическими данными, формирует один
включительный набор строк и возвращает `ResolvedReportDefinition`. Preview, PDF/печать и
CSV/XLSX не вычисляют границы повторно.

## Где используется

- Print Center: один resolved range для preview и итогового job;
- Masterlog: один depth range для preview, PDF и системного preview;
- экспорт выбранного интервала: одинаковые curve IDs и строки для CSV/XLSX;
- Report Passport: canonical payload и SHA-256 definition сохраняются в sidecar.

Для планшета сохраняется выбранный `vertical_index_id`; DEPTH-selection не подставляется в
TIME-view. Формат проекта остаётся v16.

Полный инженерный контракт: [REPORT_DEFINITION.md](../REPORT_DEFINITION.md).
