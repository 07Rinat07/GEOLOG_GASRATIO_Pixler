# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.31, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline версии 0.7.28: Ruff чист,
mypy — 0 ошибок в 262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено.
Для среза 0.7.31 выполнены `compileall`, сборка wheel и доступная headless-регрессия:
714 тестов пройдено, 4 платформенных сценария пропущено. Полный сбор pytest в текущем
контейнере останавливается на 95 Qt/LAS-зависимых модулях, потому что отсутствуют PySide6,
pyqtgraph и lasio. Ruff и mypy также недоступны. Поэтому сборка остаётся тестовой до
повторного полного gate и Windows/HiDPI/PDF/physical-print smoke-test.

## Подтверждённая рабочая основа

- LAS 1.2/2.0, CSV/TXT/Excel и GeoScape/Paradox workflows;
- безопасные копии, таблица LAS, операции над кривыми, Undo/Redo и формулы;
- проект с несколькими datasets и индексами, формат проекта 15;
- синхронный многотрековый планшет, формы, интервалы и литология;
- редактируемый Masterlog, header/forms, PDF и Print Center;
- крупные и промежуточные сетки экрана/печати с сохранением в форме;
- синхронное выделение интервала `Shift + ЛКМ`, статистика и XLSX/CSV;
- аннотации, project assets и миграции старых проектов;
- синхронные наборы пользовательских документов RU/KK/EN.

## Результаты проверки

| Проверка | Фактический результат |
|---|---|
| Полный baseline 0.7.28 | 1217 тестов пройдено, 10 пропущено; Ruff чист; mypy — 0 ошибок в 262 файлах |
| Срез 0.7.31 | 714 доступных headless/regression/source-integrity тестов пройдено, 4 пропущено; `compileall` и wheel 0.7.31 завершены без ошибок |
| Project model boundary | `MainWindow` не меняет dirty/collections/layout напрямую; tablet gestures проходят через headless mutation/controller boundary |
| Derived datasets | отменённый merge/external-LAS export транзакционно удаляет временный dataset и восстанавливает selection/dirty |
| Project assets | batch image assets валидируются целиком и устанавливаются через `MasterlogTemplateController` |
| Session binding | 27 session-aware контроллеров перепривязываются единым реестром со сбросом историй и временного состояния |
| Физическая печать/HiDPI | требует подтверждения на целевой Windows-машине |

## Технический долг с наибольшим риском

- `tablet/tablet_view.py` и `ui/main_window.py` остаются крупными orchestration-классами;
- полный Ruff/mypy/Qt/LAS gate 0.7.31 нужно повторить в окружении со всеми зависимостями;
- отсутствуют golden fixtures для общей экранной и печатной геометрии;
- Semantic Channel Dictionary и единый Import Review ещё не реализованы.

## Следующая контрольная точка

Следующий вертикальный срез — Semantic Channel Dictionary: canonical kind, quantity class,
UOM, aliases, source/sensor и исходная мнемоника. После него — единый Import Review и Report
Passport. Ручной Windows GUI/HiDPI/PDF/physical-print smoke-test остаётся обязательным условием
stable-выпуска.

Подробности: [аудит](PRODUCT_AUDIT_2026.md), [план](PROJECT_PLAN.md),
[roadmap](ROADMAP.md), [проверки](TESTING.md).
