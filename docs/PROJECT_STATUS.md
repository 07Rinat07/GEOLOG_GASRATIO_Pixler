# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.37, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline 0.7.28: Ruff чист, mypy — 0 ошибок
в 262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено. Для 0.7.37 выполнены
`compileall` и доступная headless/regression/source-integrity регрессия: 876 тестов пройдено,
4 платформенных сценария пропущено, 3 LAS-сценария исключены без `lasio`. Полная коллекция
обнаруживает 82 Qt/pyqtgraph/LAS-зависимых test-файла, которые не собираются без `PySide6`,
`pyqtgraph` и `lasio`; один дополнительно собираемый UX-файл требует Qt fixture во время запуска.
Ruff и mypy в контейнере отсутствуют. Сборка остаётся тестовой до повторного полного gate и
Windows/HiDPI/PDF/physical-print матрицы.

## Подтверждённая рабочая основа

- проект формата v16 с несколькими datasets/indexes и semantic bindings;
- интерактивный Import Review и атомарный commit;
- Report Passport schema v2 и deterministic render goldens;
- immutable `ReportDefinition` schema v2 с миграцией payload v1;
- один resolved interval для Print Center preview/output, Masterlog и selected CSV/XLSX;
- единая coverage schema v1 для zero, missing sample и unavailable channel;
- синхронная документация и пользовательские инструкции RU/KK/EN.

## Результаты текущего среза

| Проверка | Результат |
|---|---|
| Coverage states | `observed_value`, `observed_zero`, `missing_sample`, `channel_unavailable` |
| ReportDefinition | curve IDs + expected mnemonics, unavailable list и coverage фактического interval |
| CSV/TSV | `0` для нуля, пустая ячейка для missing, `#N/A` для unavailable |
| XLSX | Data + Parameters с availability/observed/zeros/missing/coverage |
| JSON/Parquet | structured coverage payload для каждой кривой |
| Interval statistics | availability, observed, zeros, missing, coverage, min/max/mean |
| Curve Catalog | общий coverage analyzer вместо отдельного подсчёта |
| Report Passport | schema v2 подписывает coverage snapshot и unavailable requests |
| Целевые проверки | 57 passed, 1 optional Parquet scenario skipped |
| Wheel | `geolog_gasratio_pixler-0.7.37-py3-none-any.whl`, metadata version 0.7.37 |
| Доступная регрессия | 876 passed, 4 skipped, 3 LAS tests deselected |
| Project format | остаётся v16 |

## Технический долг с наибольшим риском

- повторить полный Ruff/mypy/Qt/LAS gate в установленном окружении;
- выполнить Windows/HiDPI/PDF/physical-print smoke-test;
- объединить запись output и passport sidecar в одну filesystem-транзакцию;
- добавить output-file fingerprint после успешной записи артефакта;
- проверить A4/A3/custom/roll, 100%/fit и продолжение страниц на реальных устройствах.

## Следующая контрольная точка

Следующий вертикальный срез — A4/A3/custom/roll, режимы 100%/fit, page continuation и
физический printer gate на основе общего `ReportDefinition` и coverage-контракта.

Подробности: [Coverage model](COVERAGE_MODEL.md), [ReportDefinition](REPORT_DEFINITION.md),
[Report Passport](REPORT_PASSPORT.md), [план](PROJECT_PLAN.md) и [проверки](TESTING.md).
