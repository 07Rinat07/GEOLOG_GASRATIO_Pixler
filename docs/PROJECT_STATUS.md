# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.40, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline 0.7.28: Ruff чист, mypy — 0 ошибок
в 262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено. Для 0.7.40 выполнены
`compileall`, целевой DOCX/HTML/transaction/passport набор и доступная headless-регрессия.
Фактические цифры текущего контейнера приведены в таблице ниже. Полная коллекция по-прежнему
требует `PySide6`, `pyqtgraph` и `lasio`; Ruff и mypy в контейнере отсутствуют. Сборка остаётся
тестовой до повторного полного gate и Windows Word/browser/PDF/HiDPI/physical-print smoke-test.

## Подтверждённая рабочая основа

- проект формата v16 с несколькими datasets/indexes и semantic bindings;
- immutable `ReportDefinition` schema v2 и Coverage schema v1;
- Report Passport schema v4 с fingerprints готовых output artifacts;
- recoverable report-output transaction schema v1;
- CSV/XLSX/DOCX/HTML из одного resolved interval;
- deterministic DOCX OOXML и self-contained HTML без внешних ресурсов;
- единая print-media schema v1 и physical printer gate;
- синхронная документация и пользовательские инструкции RU/KK/EN.

## Результаты текущего среза

| Проверка | Результат |
|---|---|
| Общая модель | `ReportDocumentModel` schema v1 |
| Источник данных | один `ResolvedReportDefinition` и его row indices |
| Coverage | `0`, missing `—`, unavailable `#N/A` различаются явно |
| DOCX | deterministic OOXML, без макросов и внешних объектов |
| HTML | один UTF-8 файл, inline CSS, без scripts/network resources |
| Output commit | recoverable filesystem transaction schema v1 |
| Report Passport | schema v4, MIME/size/SHA-256 готового DOCX/HTML |
| Целевые проверки | 73 passed |
| Доступная регрессия | 926 passed, 4 skipped, 3 LAS-сценария deselected |
| Project format | остаётся v16 |

## Технический долг с наибольшим риском

- повторить полный Ruff/mypy/Qt/LAS gate в установленном окружении;
- выполнить Windows Word/LibreOffice/browser smoke-test для кириллицы, больших таблиц и печати;
- выполнить Windows/NTFS/network-share recovery и physical-print smoke-test;
- добавить versioned user DOCX templates только как отдельное расширение общей document model.

## Следующая контрольная точка

Следующий вертикальный срез — типизированные operational events: drilling, gas, show, sample,
casing и formation top с единым storage/QC/ReportDefinition contract.

Подробности: [DOCX/HTML adapters](DOCX_HTML_EXPORT.md),
[Report Passport](REPORT_PASSPORT.md), [план](PROJECT_PLAN.md) и [проверки](TESTING.md).
