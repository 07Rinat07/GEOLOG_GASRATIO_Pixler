# Единая ReportDefinition

`ReportDefinition` — неизменяемый прикладной контракт, который фиксирует, **что именно**
должно попасть в preview, PDF/печать и табличный экспорт. Он разрешается один раз против
конкретного `Dataset`, после чего все последующие адаптеры используют одинаковый индекс,
интервал и состав каналов.

## Схема v2

Определение содержит:

- стабильный `definition_id` и имя;
- профиль: view, masterlog, geology, cuttings, calcimetry, LBA, gas, drilling, events или combined;
- конкретные `dataset_id` и `index_id`;
- язык RU/KK/EN;
- выбранные curve IDs, ожидаемые `channel_mnemonics` и типизированные разделы;
- ссылку на форму/layout через kind, ID и content-addressed revision;
- режим интервала и дополнительные детерминированные options.

Payload сериализуется в canonical JSON и имеет `content_sha256`. Нестабильные поля — время,
абсолютный output path и случайные runtime ID — в контракт не входят.

## Один интервал

Поддерживаются четыре режима:

| Режим | Источник границ |
|---|---|
| `full` | полный диапазон зафиксированного индекса |
| `current` | viewport, замороженный при открытии Print Center |
| `custom` | явно введённые начало и конец |
| `selection` | синхронное выделение dataset, если оно относится к той же оси |

`resolve_report_definition()`:

1. проверяет dataset и точный index ID без скрытого переключения оси;
2. нормализует порядок границ и ограничивает их реальным диапазоном индекса;
3. формирует включительный массив строк и `sample_count`;
4. строго проверяет curve IDs, разрешает ожидаемые мнемоники и сохраняет ненайденные как unavailable;
5. рассчитывает coverage с отдельными zero/missing/unavailable состояниями;
6. возвращает `ResolvedReportDefinition`, который становится единственным источником диапазона.

Числовые и datetime-индексы используют один контракт. Print Center сейчас принимает числовую
вертикальную ось; табличный интервальный экспорт — активный глубинный индекс.

## Подключённые сценарии

- **Print Center:** preview и file/physical-print job получают один resolved definition;
  downstream pagination переводится в точный custom range, поэтому повторного чтения viewport нет.
- **Selected interval CSV/XLSX:** один selection definition разрешается до открытия exporter;
  CSV и Excel используют те же границы и curve IDs.
- **Masterlog:** preview, PDF и системный preview используют одну definition и нормализованный
  depth range.
- **Report Passport:** sidecar хранит полный payload definition и его digest вместе с
  фактически разрешённым интервалом.

Для планшета фиксируется `vertical_index_id` выбранного layout. Глубинное выделение доступно
в Print Center только когда оно относится к тому же активному индексу, поэтому TIME-view не
может случайно получить DEPTH-selection.

## Архитектурное правило

UI может выбрать режим, границы, форму и язык, но не должен самостоятельно вычислять набор
строк для каждого exporter. Любой новый PDF, CSV, XLSX, TSV или preview-сценарий должен:

1. создать `ReportDefinition`;
2. один раз получить `ResolvedReportDefinition`;
3. использовать только `resolved.interval`, `resolved.curve_ids`, `resolved.coverage` и payload definition;
4. передать тот же definition snapshot в Report Passport.

Project format v19 хранит `well.operational_events` и `well.acquisition_sessions`; events были введены в v17. Для разделов `EVENTS` и `DRILLING`
`resolve_operational_event_report()` использует точные границы уже готового
`ResolvedReportDefinition`: depth → `depth_m`, relative time → `elapsed_time_s`, datetime →
UTC `measured_at`. Option `event_kinds` задаёт список discriminator через запятую. Интервал
повторно не вычисляется.

Payload schema v1 читается как legacy и мигрируется в runtime schema v2. Подробнее о состояниях данных: [COVERAGE_MODEL.md](COVERAGE_MODEL.md).
