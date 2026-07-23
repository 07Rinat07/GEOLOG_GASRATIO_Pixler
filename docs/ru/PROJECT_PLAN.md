# План проекта

Актуально на 23 июля 2026 года. История версий находится в release notes; здесь только
действующий план.

## P0 — стабильность выпуска

- [x] исправить маршрутизацию аннотаций и аварийное завершение полного Qt-теста;
- [x] довести Ruff и mypy до нулевого числа ошибок; полный pytest: 1196 пройдено,
  10 пропущено;
- выполнить Windows/HiDPI/PDF/физическую печать по обязательной матрице;
- не объявлять сборку стабильной до зелёного gate.

## P0 — архитектура и данные

- [x] первым срезом выделить annotation event router из `TabletView` без изменения поведения
  и покрыть его headless-тестами;
- [x] вынести pan/zoom/home/end/keyboard в headless navigation coordinator;
- [x] вынести plan/order/reuse треков и сохранить экземпляры графиков при Undo/Redo;
- [x] вынести создание, rollback и удаление треков с очисткой связанных реестров;
- затем вынести сетку и режимы редактирования;
- разделить `MainWindow` на команды workspace, import, print и session binding;
- создать Semantic Channel Dictionary: тип параметра, quantity class, UOM, aliases,
  источник и исходная мнемоника;
- добавить единый Import Review и паспорт воспроизводимости отчёта.

## P1 — операции и real-time

- типизированные drilling/gas/show/sample/casing/top события;
- QC для gap, duplicate, out-of-order, stale и calibration;
- версионированная lag/depth correction без изменения источника;
- WITSML 2.1 inventory, затем replay, затем защищённый ETP 1.2 client.

## P1 — отчёты

- одна модель интервала для preview, PDF и табличного экспорта;
- единые bindings, UOM, coverage и различение нуля/пропуска;
- проверка A4/A3/custom/roll, 100%/fit и продолжения страниц.

## P2 — развитие

- multiwell correlation с tops/ties и PDF;
- crossplots и статистические графики;
- ограниченный версионированный API и Python console с журналом и разрешениями.

Полные критерии: [общий план](../PROJECT_PLAN.md). Основание:
[аудит](PRODUCT_AUDIT_2026.md).
