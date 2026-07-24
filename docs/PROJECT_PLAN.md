# План проекта

Актуально на 24 июля 2026 года. Hotfix 0.7.51 сохраняет project format v20, form schema v6 и
tablet layout v16. После Windows-подтверждения исправлений следующий предметный этап —
read-only offline WITSML 2.1 inventory и mapping fixtures.

## P0 — hotfix 0.7.51: диагностика и безопасный lifecycle карандаша

- [x] вести вращаемый UTF-8 журнал в каталоге данных приложения;
- [x] записывать необработанные Python/thread exceptions и полный traceback;
- [x] перехватывать Qt messages и исключения, вышедшие из Qt event handlers;
- [x] журналировать form apply/preview/rollback, tablet render и curve-pencil commit;
- [x] добавить команды открытия журнала, копирования пути и создания diagnostics ZIP;
- [x] исключить из diagnostics ZIP значения LAS, проектные assets и сохранённые формы;
- [x] после карандаша обновлять только затронутые curve tracks без полного rebuild;
- [x] сохранять размеры колонок, scroll position и остальные виджеты формы после штриха;
- [x] перед полным rebuild выключать карандаш и очищать stale track/curve targets;
- [x] перед form apply сначала проверять candidate model, затем завершать pencil mode;
- [x] покрыть logging, bundle privacy и lifecycle source contracts headless-тестами;
- [ ] выполнить Windows/PySide6 smoke-test: рисование в нескольких колонках, Undo/Redo и не менее
  20 переходов между формами после штриха без повреждения layout и Qt lifecycle errors.

Критерий 0.7.51: после рисования планшет не меняет форму и размеры колонок; переход на другую
форму остаётся рабочим; при любой ошибке пользователь может создать один diagnostics ZIP с
traceback и последовательностью системных событий.

## Следующие этапы

- [ ] read-only offline WITSML 2.1 inventory и mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays в одной форме;
- [ ] directory watcher с preview-подтверждением ежедневного прироста;
- [ ] secured ETP 1.2 только после успешного fixture replay.
