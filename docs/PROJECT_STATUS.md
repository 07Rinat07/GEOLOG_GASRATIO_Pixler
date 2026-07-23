# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.41, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline 0.7.28: Ruff чист, mypy — 0 ошибок
в 262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено. Для 0.7.41 выполнены
`compileall`, расширенный целевой набор и доступная headless-регрессия. Полный набор
по-прежнему требует `PySide6`, `pyqtgraph`, `lasio`, Ruff и mypy. Сборка остаётся тестовой до
повторного полного gate и Windows/HiDPI/PDF/physical-print smoke-test.

## Подтверждённая рабочая основа

- project format v17 с безопасной миграцией v16 → v17;
- immutable operational-event schema v1 для drilling/gas/show/sample/casing/formation-top;
- depth/time anchors, canonical UTC timestamps, source, revision и calibration metadata;
- детерминированный QC: duplicate, out-of-order, gap, stale, calibration missing/expired;
- единственная изменяющая граница `OperationalEventController` с optimistic revision;
- строгий discriminator codec и round-trip typed payload;
- EVENTS/DRILLING projection из точного `ResolvedReportDefinition` interval;
- существующие ReportDefinition v2, Coverage v1, Passport v4 и output transaction v1;
- удалены устаревшие дубликаты import-controller из `ui`, рабочая граница остаётся в `services`.

## Результаты текущего среза

| Проверка | Результат |
|---|---|
| Domain | 6 typed payload kinds и общий immutable envelope |
| Storage | `Well.operational_events`, project format v17 |
| Migration | v16 → v17 без изменения существующих данных |
| QC | duplicate/out-of-order/gap/stale/calibration |
| Mutation | create/update/remove через controller и revision conflict |
| Report | depth, relative-time и datetime projection из resolved interval |
| Негативные сценарии | unknown kind/field, payload mismatch, cross-well, duplicate ID |
| Расширенный целевой набор | 108 passed |
| Доступная headless-регрессия | 936 passed, 4 skipped |

## Технический долг с наибольшим риском

- повторить полный Ruff/mypy/Qt/LAS gate в установленном окружении;
- выполнить Windows/NTFS/network-share и physical-print smoke-test;
- добавить UI/import adapters поверх controller, не обходя mutation boundary;
- определить persisted acquisition/checkpoint contract до начала WITSML/ETP.

## Следующая контрольная точка

Следующий вертикальный срез — append-only growing dataset, checkpoint и детерминированный
replay. Критерий: записанный поток повторно создаёт те же events, QC flags и отчёт.

Подробности: [Operational events](OPERATIONAL_EVENTS.md), [план](PROJECT_PLAN.md) и
[проверки](TESTING.md).
