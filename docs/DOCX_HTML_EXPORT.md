# DOCX и HTML export adapters

Статус: реализовано в версии 0.7.40. Runtime model: `report-document/v1`.
Формат проекта остаётся v16. Report Passport остаётся schema v4.

## Назначение

DOCX и HTML формируют редактируемое или переносимое представление выбранного отчётного
интервала. Они не создают отдельную модель данных и не пересчитывают диапазон повторно.
Адаптеры получают готовый `ResolvedReportDefinition`, поэтому используют те же:

- dataset и точный index ID;
- включительные row indices;
- curve IDs и ожидаемые channel mnemonics;
- Coverage snapshots;
- язык RU/KK/EN;
- ReportDefinition SHA-256.

## Общая document model

`data/report_document_export.py` строит Qt-независимую `ReportDocumentModel` schema v1.
Она содержит параметры отчёта, coverage-таблицу и строки данных. Значения отображаются
одинаково в обоих форматах:

| Состояние | DOCX/HTML |
|---|---|
| наблюдаемое значение | десятичное значение |
| реальный ноль | `0` |
| пропущенный отсчёт | `—` |
| недоступный канал | `#N/A` |

Coverage-таблица публикует availability, observed, zeros, missing и coverage percent для
каждого запрошенного канала.

## DOCX adapter

DOCX создаётся как детерминированный OOXML-пакет стандартной библиотекой Python, без новой
обязательной runtime-зависимости. Пакет содержит только безопасные XML-части:

- основной документ;
- стили;
- core/application properties;
- package/document relationships.

Макросы, внешние ссылки, embedded objects и удалённые ресурсы не добавляются. Документ
использует A4 landscape, повторяемые таблицы параметров, coverage и данных. Одинаковая
модель создаёт одинаковые байты DOCX в одном runtime.

## HTML adapter

HTML является одним UTF-8-файлом с inline CSS. Он не содержит внешних stylesheet, script,
изображений или сетевых ссылок. Значения coverage получают явные `data-state` и CSS-классы,
а print stylesheet повторяет заголовок таблицы на страницах браузерной печати.

## Filesystem transaction и Passport

UI передаёт producer в `execute_report_output_transaction()`:

1. DOCX/HTML пишется только в staging;
2. готовые байты получают MIME, размер и SHA-256;
3. Passport v4 повторно подписывается;
4. output и sidecar устанавливаются одной journaled-транзакцией;
5. rollback восстанавливает предыдущую пару после частичного commit.

`load_report_passport()` повторно проверяет фактический DOCX/HTML. Любое изменение после
экспорта обнаруживается как несовпадение fingerprint.

## Ограничения

DOCX/HTML текущего среза — структурированные интервальные отчёты. Они не пытаются полностью
повторить графическую геометрию Masterlog или Print Center; канонической печатной формой
остаётся PDF. Версионированные пользовательские DOCX-шаблоны являются отдельным будущим
расширением поверх уже готовой document model.
