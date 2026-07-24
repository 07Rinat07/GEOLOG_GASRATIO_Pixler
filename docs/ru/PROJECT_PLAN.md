# План проекта

Актуально на 24 июля 2026 года. Hotfix 0.7.50 сохраняет project format v20, form schema v6 и
tablet layout v16. Следующий предметный этап после Windows-подтверждения — read-only offline
WITSML 2.1 inventory и mapping fixtures.

## P0 — hotfix 0.7.50: безопасный жизненный цикл форм

- [x] останавливать debounce-таймеры шапки до удаления старого Qt-дерева;
- [x] блокировать сигналы minimum, maximum, unit и scale при disposal;
- [x] снимать event filters трека до `deleteLater`;
- [x] запрещать обработку header mutations во время layout transaction/rebuild;
- [x] восстанавливать форму только из deep-copied `TabletLayout`, не сохраняя ссылки на widgets;
- [x] использовать один исходный rollback snapshot для принятой формы;
- [x] убрать повторный rollback в Form Manager после reversible apply;
- [x] сохранить отдельный rollback исходной формы при Cancel после preview;
- [x] покрыть disposal, single rollback и rebuild guard headless-тестами;
- [ ] выполнить Windows/PySide6 smoke-test: 20 последовательных переключений между широкими и
  узкими формами, включая редактирование minimum/maximum непосредственно перед переключением.

Критерий 0.7.50: формы можно многократно переключать без `Internal C++ object already deleted`;
при любой ошибке остаётся полностью рабочая предыдущая форма, а не частично построенный планшет.

## Следующие этапы

- [ ] read-only offline WITSML 2.1 inventory и mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays в одной форме;
- [ ] directory watcher с preview-подтверждением ежедневного прироста;
- [ ] secured ETP 1.2 только после успешного fixture replay.
