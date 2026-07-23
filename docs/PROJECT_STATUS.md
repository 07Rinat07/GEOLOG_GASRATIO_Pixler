# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.32, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline версии 0.7.28: Ruff чист,
mypy — 0 ошибок в 262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено.
Для среза 0.7.32 выполнены `compileall`, сборка wheel и доступная headless-регрессия:
707 тестов пройдено, 4 платформенных сценария пропущено. Полный сбор pytest в текущем
контейнере останавливается на 95 Qt/LAS-зависимых модулях, потому что отсутствуют PySide6,
pyqtgraph и lasio. Ruff и mypy также недоступны. Поэтому сборка остаётся тестовой до
повторного полного gate и Windows/HiDPI/PDF/physical-print smoke-test.

## Подтверждённая рабочая основа

- LAS 1.2/2.0, CSV/TXT/Excel и GeoScape/Paradox workflows;
- безопасные копии, таблица LAS, операции над кривыми, Undo/Redo и формулы;
- проект с несколькими datasets и индексами, формат проекта 16;
- единый Semantic Channel Dictionary поверх каталога Sensors;
- сохранённый semantic binding каждой кривой: canonical kind/mnemonic, quantity class,
  canonical/source UOM, aliases, sensor/source, исходная мнемоника, confidence и evidence;
- read-only headless-модель Import Review для индекса, NULL, UOM-конфликтов, unresolved и
  duplicate canonical kinds;
- синхронный многотрековый планшет, формы, интервалы и литология;
- редактируемый Masterlog, header/forms, PDF и Print Center;
- аннотации, project assets и миграции старых проектов;
- синхронные наборы пользовательских документов RU/KK/EN.

## Результаты проверки

| Проверка | Фактический результат |
|---|---|
| Полный baseline 0.7.28 | 1217 тестов пройдено, 10 пропущено; Ruff чист; mypy — 0 ошибок в 262 файлах |
| Срез 0.7.32 | 707 доступных headless/regression/source-integrity тестов пройдено, 4 пропущено; `compileall` и wheel 0.7.32 завершены без ошибок |
| Semantic dictionary | CSV/Excel, LAS и Paradox создают один сериализуемый binding; неизвестные каналы/UOM остаются явными |
| Project format v16 | semantic binding сохраняется и восстанавливается; legacy curves обогащаются при чтении без перезаписи прежнего canonical решения |
| Derived curves | copy, transfer, merge, reverse/resample и TIME↔DEPTH сохраняют semantic snapshot |
| Import Review core | детерминированно показывает индекс, confidence, NULL, unresolved, UOM conflict и duplicate canonical kind без изменения dataset |
| Физическая печать/HiDPI | требует подтверждения на целевой Windows-машине |

## Технический долг с наибольшим риском

- `tablet/tablet_view.py` и `ui/main_window.py` остаются крупными orchestration-классами;
- полный Ruff/mypy/Qt/LAS gate 0.7.32 нужно повторить в окружении со всеми зависимостями;
- отсутствуют golden fixtures для общей экранной и печатной геометрии;
- Import Review пока является headless/read-only контрактом: интерактивное подтверждение,
  ручные overrides и единая commit-граница ещё не реализованы.

## Следующая контрольная точка

Следующий вертикальный срез — единый интерактивный Import Review поверх готовой headless-модели:
индекс, mapping, единицы, NULL, QC, ручные semantic overrides и атомарное подтверждение импорта.
После него — Report Passport. Ручной Windows GUI/HiDPI/PDF/physical-print smoke-test остаётся
обязательным условием stable-выпуска.

Подробности: [Semantic Channel Dictionary](SEMANTIC_CHANNEL_DICTIONARY.md),
[аудит](PRODUCT_AUDIT_2026.md), [план](PROJECT_PLAN.md), [roadmap](ROADMAP.md),
[проверки](TESTING.md).
