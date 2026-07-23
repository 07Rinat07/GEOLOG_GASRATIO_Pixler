# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.39, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline 0.7.28: Ruff чист, mypy — 0 ошибок
в 262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено. Для 0.7.39 выполнены
`compileall`, 37 целевых transaction/passport/source-integrity тестов и доступная регрессия:
915 тестов пройдено, 4 платформенных сценария пропущено, 3 LAS-сценария исключены без `lasio`.
Полная коллекция обнаруживает 82 Qt/pyqtgraph/LAS-зависимых файла, которые не собираются без
`PySide6`, `pyqtgraph` и `lasio`; ещё один UX-файл требует Qt во время выполнения. Ruff и mypy
в контейнере отсутствуют. Сборка остаётся тестовой до повторного полного gate и Windows
filesystem/PDF/HiDPI/physical-print smoke-test.

## Подтверждённая рабочая основа

- проект формата v16 с несколькими datasets/indexes и semantic bindings;
- интерактивный Import Review и атомарный commit данных;
- immutable `ReportDefinition` schema v2 и Coverage schema v1;
- Report Passport schema v4 с fingerprints готовых output artifacts;
- recoverable report-output transaction schema v1;
- один resolved interval для preview/output, Masterlog и tabular export;
- единая print-media schema v1 для A4/A3/custom/roll, Fit/100% и continuations;
- physical printer gate после системного выбора устройства;
- синхронная документация и пользовательские инструкции RU/KK/EN.

## Результаты текущего среза

| Проверка | Результат |
|---|---|
| Staging | renderer/exporter не пишет непосредственно в окончательный путь |
| Journal | schema v1: rendering → prepared → backed-up → committed |
| Rollback | прежние output и sidecar восстанавливаются после частичного commit |
| Recovery | незавершённый commit откатывается; committed-состояние завершает cleanup |
| Output fingerprint | basename, role/page, MIME, byte size и SHA-256 |
| Tamper detection | `load_report_passport()` проверяет JSON и фактические output bytes |
| Overwrite | устаревшие `*_page_NNN.*` удаляются транзакционно |
| Report Passport | schema v4 |
| Целевые проверки | 37 passed |
| Доступная регрессия | 915 passed, 4 skipped, 3 LAS tests deselected |
| Project format | остаётся v16 |

## Технический долг с наибольшим риском

- повторить полный Ruff/mypy/Qt/LAS gate в установленном окружении;
- выполнить Windows/NTFS/network-share recovery smoke-test с принудительным завершением процесса;
- выполнить Windows/HiDPI/PDF/physical-print smoke-test;
- добавить DOCX и HTML adapters поверх готовых ReportDefinition/Coverage/transaction contracts.

## Следующая контрольная точка

Следующий вертикальный срез — DOCX и HTML export adapters через общую `ReportDefinition`,
Coverage, output transaction и Report Passport schema v4.

Подробности: [filesystem-транзакция](REPORT_OUTPUT_TRANSACTION.md),
[Report Passport](REPORT_PASSPORT.md), [план](PROJECT_PLAN.md) и [проверки](TESTING.md).
