# План проекта

Актуально на 24 июля 2026 года. Hotfix **0.7.59** сохраняет project format v20, form schema v6 и tablet layout v16.

## P0 — hotfix 0.7.59: безопасное переключение плотных локализованных форм

- [x] инициализировать localizer в каждом `TabletTrackWidget`;
- [x] передавать активный localizer из `TabletView` во все новые треки;
- [x] сохранить fallback для прямого создания виджета в тестах и plugins;
- [x] покрыть source-contract проверкой место создания трека;
- [x] добавить Qt regression-тест формы с семью параметрами и overflow-tooltip;
- [x] синхронизировать status, changelog, testing и release notes RU/KK/EN;
- [ ] Windows/PySide6: несколько раз переключить плотные формы на RU/KK/EN и проверить rollback.

Критерий выхода: форма с внутренней прокруткой шапки применяется без `AttributeError`, а при любой другой ошибке остаётся предыдущая рабочая форма.

## Следующие этапы

- [ ] read-only offline WITSML 2.1 inventory и mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays в одной форме;
- [ ] directory watcher с preview-подтверждением ежедневного прироста;
- [ ] secured ETP 1.2 только после успешного fixture replay.
