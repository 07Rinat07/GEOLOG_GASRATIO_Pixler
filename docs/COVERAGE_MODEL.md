# Единая coverage-модель

Статус: реализовано в версии 0.7.37. Runtime schema coverage: v1. `ReportDefinition` и
`Report Passport` использует schema v3. Формат проекта остаётся v16.

## Инженерная семантика

Для каждого запрошенного канала и каждого разрешённого интервала используются четыре состояния:

| Состояние | Значение |
|---|---|
| `observed_value` | канал доступен, отсчёт конечный и не равен нулю |
| `observed_zero` | канал доступен, отсчёт конечный и физически равен `0.0` |
| `missing_sample` | канал доступен, но отсчёт представлен `NaN` или `Infinity` |
| `channel_unavailable` | канал был запрошен отчётом или формой, но отсутствует в dataset |

Ноль никогда не преобразуется в NULL. Пустой отсчёт никогда не подменяется нулём. Отсутствующий
канал не считается серией пропущенных отсчётов: это отдельное состояние доступности.

## ChannelCoverage

Headless-модуль `services/coverage.py` формирует детерминированный `ChannelCoverage`:

- `total_count` — число строк разрешённого интервала;
- `observed_count` — количество конечных отсчётов, включая нули;
- `zero_count` — количество реальных нулей;
- `missing_count` — количество нечисловых/не конечных отсчётов доступного канала;
- `unavailable_count` — число строк, для которых канал отсутствует целиком;
- coverage, missing и zero percentages;
- `primary_state` для краткого представления канала.

Coverage считается только по строкам `ResolvedReportDefinition`. Строки с невалидным индексом,
которые не вошли в отчётный интервал, не влияют на статистику.

## ReportDefinition schema v2

Помимо стабильных curve IDs, definition может хранить `channel_mnemonics` на уровне всего отчёта
и отдельного section. Resolver:

1. проверяет стабильные curve IDs как строгие ссылки;
2. разрешает мнемоники через dataset;
3. добавляет найденные curve IDs;
4. сохраняет ненайденные мнемоники как `unavailable_channel_mnemonics`;
5. формирует coverage для всех доступных и недоступных каналов.

Payload schema v1 читается и мигрируется в runtime schema v2. Проектный JSON не изменён.

## Экспорт

### CSV/TSV

- реальный ноль экспортируется как `0`;
- `missing_sample` экспортируется пустой ячейкой;
- `channel_unavailable` экспортируется отдельной колонкой с `#N/A`.

### XLSX

Лист `Data` использует те же значения. Лист `Parameters` дополнительно содержит availability,
observed, zeros, missing и coverage для каждого индекса и канала.

### JSON и Parquet

Каждая кривая получает структурированный coverage payload. Числовые значения при этом не
изменяются: конечный ноль остаётся нулём, не конечное значение остаётся nullable.

## Report Passport schema v3

Sidecar подписывает coverage snapshot для фактического интервала отчёта. Для недоступного
канала сохраняются мнемоника, `availability=unavailable`, `primary_state=channel_unavailable` и
`unavailable_count`. Поэтому два отчёта с одинаковыми значениями, но разным составом доступных
каналов, имеют разные `passport_sha256`.

## Архитектурное правило

Новый renderer, report section или exporter не должен самостоятельно считать coverage через
`np.isfinite()` и терять семантику доступности. Он должен использовать `ChannelCoverage` из
разрешённого report contract либо общий анализатор coverage.
