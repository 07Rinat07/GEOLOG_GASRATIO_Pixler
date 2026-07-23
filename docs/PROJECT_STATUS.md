# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.38, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline 0.7.28: Ruff чист, mypy — 0 ошибок
в 262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено. Для 0.7.38 выполнены
`compileall`, целевые print/report/source-integrity проверки и доступная регрессия: 910 тестов
пройдено, 4 платформенных сценария пропущено, 3 LAS-сценария исключены без `lasio`.
Полная коллекция обнаруживает 82 Qt/pyqtgraph/LAS-зависимых файла, которые не собираются без
`PySide6`, `pyqtgraph` и `lasio`; ещё один Qt UX-сценарий исключён из доступного запуска.
Ruff и mypy в контейнере отсутствуют. Сборка остаётся тестовой до повторного полного gate и
подписанной Windows/HiDPI/PDF/physical-print матрицы на реальных устройствах.

## Подтверждённая рабочая основа

- проект формата v16 с несколькими datasets/indexes и semantic bindings;
- интерактивный Import Review и атомарный commit;
- immutable `ReportDefinition` schema v2 и Coverage schema v1;
- Report Passport schema v3 и deterministic render goldens;
- один resolved interval для preview/output, Masterlog и tabular export;
- единая print-media schema v1 для A4/A3/custom/roll, Fit/100% и continuations;
- physical printer gate после системного выбора устройства;
- синхронная документация и пользовательские инструкции RU/KK/EN.

## Результаты текущего среза

| Проверка | Результат |
|---|---|
| Media | A4, A3, custom 25–5000 мм, roll с длиной до 5000 мм на сегмент |
| Scale | Fit или 100% при reference DPI 96 |
| Continuation | декартово произведение vertical pages × horizontal continuations |
| Page range | системный диапазон `1…N`; gate и результат учитывают выбранные страницы |
| Printer gate | device state, media support, bounds, margins, printable area, DPI, page feed |
| Direct export | PDF поддерживает continuations; однофайловый raster/SVG не обрезает их молча |
| Report Passport | schema v3 подписывает scale mode и continuation overlap |
| Целевые проверки | 56 passed |
| Print-specific contract | 27 passed |
| Доступная регрессия | 910 passed, 4 skipped, 3 LAS tests deselected |
| Project format | остаётся v16 |

## Технический долг с наибольшим риском

- повторить полный Ruff/mypy/Qt/LAS gate в установленном окружении;
- выполнить Windows/HiDPI/PDF/physical-print smoke-test для A4/A3/custom/roll и Fit/100%;
- объединить запись output и passport sidecar в одну восстанавливаемую filesystem-транзакцию;
- добавить output-file fingerprint после успешной записи артефакта.

## Следующая контрольная точка

Следующий вертикальный срез — единая filesystem-транзакция для output + Report Passport и
fingerprint уже записанного выходного файла.

Подробности: [модель печати](PRINT_MEDIA_MODEL.md), [Report Passport](REPORT_PASSPORT.md),
[план](PROJECT_PLAN.md) и [проверки](TESTING.md).
