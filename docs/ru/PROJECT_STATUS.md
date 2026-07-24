# Статус проекта

Срез: 24 июля 2026 года. Версия пакета: **0.7.49**, исправляющая тестовая сборка.
Project format: **v20**, form schema: **v6**, tablet layout: **v16**.

## Завершено в 0.7.49

- новые и автоматически созданные кривые используют линейную шкалу по умолчанию;
- ручные minimum/maximum входят в ключ рендера и перестраивают нормализованную геометрию кривой;
- диапазон применяется автоматически после короткой паузы или сразу по Enter;
- адаптивная шапка сохраняет minimum, maximum, unit и scale type в узкой колонке;
- engineering ruler продолжает использовать major/minor divisions сетки конкретной колонки;
- новая форма рендерится до записи в session;
- ошибка render/commit восстанавливает последнюю рабочую форму, dirty-state и выбранный трек;
- отмена Form Manager после preview возвращает исходную конфигурацию;
- существующие явно сохранённые logarithmic bindings не изменяются;
- project/form/layout schema не менялись, миграция не требуется.

## Проверка

- focused header/form/transaction: **150 passed**;
- доступная headless-регрессия: **1037 passed, 4 skipped, 3 deselected**;
- `compileall` и wheel build выполнены;
- Windows smoke-test реального Qt-render, HiDPI, узких колонок и rollback обязателен из-за
  отсутствия PySide6/pyqtgraph в контейнере.

## Следующий вертикальный срез

Read-only offline WITSML 2.1 inventory и mapping fixtures. ETP 1.2 остаётся заблокирован до
fixture replay.
