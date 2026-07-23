# План проекта

Актуально на 23 июля 2026 года. История версий находится в release notes; здесь только
действующий план.

## P0 — стабильность выпуска

- [x] исправить маршрутизацию аннотаций и аварийное завершение полного Qt-теста;
- [x] довести Ruff и mypy до нулевого числа ошибок; baseline 0.7.28: 1217 тестов пройдено,
  10 пропущено;
- выполнить Windows/HiDPI/PDF/физическую печать по обязательной матрице;
- повторить полный Ruff/mypy/pytest gate для текущей версии;
- не объявлять сборку стабильной до зелёного gate.

## P0 — архитектура и данные

- [x] выделить annotation event router из `TabletView` без изменения поведения;
- [x] вынести pan/zoom/home/end/keyboard в headless navigation coordinator;
- [x] вынести plan/order/reuse, создание, rollback и удаление треков;
- [x] вынести общий renderer сетки экрана/печати;
- [x] сделать контроллер режимов единственным владельцем F4 и инструмента аннотаций;
- [x] вынести навигацию между главной, workspace и целевой вкладкой из `MainWindow`;
- [x] вынести маршрутизацию универсального импорта и CSV/Excel/LAS/Paradox jobs;
- [x] вынести print jobs, session binding и команды дерева проекта;
- [x] запретить UI-классам напрямую менять сериализуемую модель проекта;
- [x] создать Semantic Channel Dictionary: тип параметра, quantity class, UOM, aliases,
  источник и исходная мнемоника; binding введён в v16 и сохраняется в текущем v18;
- [x] добавить интерактивный Import Review с ручными overrides, QC preview и атомарным commit;
- [x] добавить паспорт воспроизводимости отчёта с fingerprints, bindings/UOM, версиями формул, revision формы, языком и render settings;
- [x] добавить детерминированные golden fixtures экранной и печатной сетки, legend, lithotypes и annotations;
- [x] унифицировать `ReportDefinition` и interval selection для preview, PDF и табличного экспорта;
- [x] добавить coverage и явное различение нуля, пропуска и отсутствующего канала.

## P1 — операции и real-time

- [x] типизированные drilling/gas/show/sample/casing/formation-top события, project format v17;
- [x] QC для gap, duplicate, out-of-order, stale и calibration;
- [x] append-only growing dataset, checkpoint и deterministic replay;
- [ ] версионированная lag/depth correction без изменения источника;
- [ ] offline WITSML 2.1 inventory и mapping fixtures, затем защищённый ETP 1.2 client после fixture replay.

## P1 — отчёты

- [x] одна модель интервала для preview, PDF и табличного экспорта;
- [x] единые bindings, UOM, coverage и различение нуля/пропуска/unavailable channel;
- [x] A4/A3/custom/roll, Fit/100%, продолжения и physical printer gate;
- [x] единая filesystem-транзакция output + passport и fingerprint готового файла.
- [x] DOCX и HTML adapters через общий ReportDefinition/Coverage contract и output transaction.

## P2 — развитие

- multiwell correlation с tops/ties и PDF;
- crossplots и статистические графики;
- ограниченный версионированный API и Python console с журналом и разрешениями.

Полные критерии: [общий план](../PROJECT_PLAN.md). Основание:
[аудит](PRODUCT_AUDIT_2026.md).
