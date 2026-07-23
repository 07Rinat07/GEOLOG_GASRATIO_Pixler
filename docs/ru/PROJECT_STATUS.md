# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.34, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline 0.7.28: Ruff чист, mypy — 0 ошибок
в 262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено. Для 0.7.34 выполнены
`compileall` и доступная headless/regression/source-integrity регрессия: 742 теста пройдено,
4 платформенных сценария пропущено. Ещё 4 LAS/Qt-сценария явно исключены из этого запуска из-за
отсутствующих `lasio`/`PySide6`; полная коллекция сообщает 95 ошибок импорта Qt/LAS-модулей.
Ruff и mypy в контейнере отсутствуют. Сборка остаётся тестовой до повторного полного gate и
обязательной Windows/HiDPI/PDF/physical-print матрицы.

## Подтверждённая рабочая основа

- безопасные LAS 1.2/2.0, CSV/TXT, Excel и GeoScape/Paradox workflows;
- multi-dataset/multi-index проект формата v16;
- Semantic Channel Dictionary, UOM quantity classes и сериализуемые semantic bindings;
- интерактивный Import Review с ручными overrides, QC и атомарным commit;
- детерминированный Report Passport schema v1 с SHA-256 проверкой;
- многотрековый планшет, формы, Masterlog, Print Center, интерпретационные отчёты и annotations;
- синхронные пользовательские документы RU/KK/EN.

## Результаты текущего среза

| Проверка | Результат |
|---|---|
| Детерминизм | неизменившиеся данные, форма, язык и render settings дают тот же `passport_sha256` |
| Интервал | хэшируются только значения выбранных каналов внутри фактического интервала отчёта |
| Semantic/UOM | сохраняется полный binding: sensor/source, kind, quantity, UOM, confidence, aliases и evidence |
| Источники | import snapshot, embedded LAS, внешний файл либо normalized report data имеют SHA-256 |
| Формулы | фиксируются ID, версия, provenance и SHA-256 выражения, когда оно доступно |
| Формы | Masterlog использует version, формы/layout — content-addressed revision |
| Экспорт | sidecar создаётся для Print Center, прямого PNG/SVG/PDF, Masterlog и interpretation PDF |
| Проверка JSON | загрузчик обнаруживает изменение подписанного содержимого |
| Доступная регрессия | 742 passed, 4 skipped, 4 dependency-specific scenarios deselected |
| Project format | остаётся v16 |

## Технический долг с наибольшим риском

- полный Ruff/mypy/Qt/LAS gate 0.7.34 нужно повторить в полном окружении;
- Windows/HiDPI/PDF/physical-print smoke-test остаётся обязательным;
- output и sidecar записываются атомарно по отдельности, но не одной filesystem-транзакцией;
- физическая печать вычисляет digest, но не создаёт sidecar из-за отсутствия output path;
- отсутствуют golden fixtures общей экранной и печатной геометрии;
- output-file fingerprint будет добавлен после унификации `ReportDefinition`.

## Следующая контрольная точка

Следующий вертикальный срез — golden fixtures для экранной и печатной сетки, легенд,
литотипов и аннотаций. Ручной Windows GUI/HiDPI/PDF/physical-print smoke-test остаётся
обязательным условием stable.

Подробности: [Report Passport](REPORT_PASSPORT.md), [Import Review](IMPORT_REVIEW.md),
[Semantic Channel Dictionary](SEMANTIC_CHANNEL_DICTIONARY.md), [план](PROJECT_PLAN.md) и
[проверки](../TESTING.md).
