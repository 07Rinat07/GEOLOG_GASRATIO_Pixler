# План проекта

Актуально на 24 июля 2026 года. Hotfix **0.7.52** сохраняет project format v20, form schema v6
и tablet layout v16. Следующий предметный этап после Windows-подтверждения — read-only offline
WITSML 2.1 inventory и mapping fixtures.

## P0 — hotfix 0.7.52: идемпотентная очистка Qt и компактные шапки

- [x] проверять QObject через `shiboken6.isValid()` до обращения к C++-объекту;
- [x] безопасно удалять event filters и вызывать `deleteLater()`;
- [x] продолжать освобождение остальных треков после ошибки одного wrapper;
- [x] сделать повторный reset планшета идемпотентным;
- [x] не допускать блокировки import recovery и form rollback удалённым `CurveHeaderEditor`;
- [x] уменьшить высоту редактируемой шапки до 52 px и обычной подписи до 38 px;
- [x] сохранить прямое редактирование min/unit/max и выбор linear/log;
- [x] синхронизировать инженерную линейку с сохранёнными делениями сетки;
- [x] ограничить общий пояс шапок 360 px;
- [x] добавить конкретные рекомендации для LAS duplicates/non-uniform step/gaps;
- [x] покрыть cleanup/header/diagnostics headless и source-contract тестами;
- [ ] Windows/PySide6: импортировать проблемный LAS, выполнить 20 form switches и 20 reset без
  `already deleted`, затем проверить широкие и узкие колонки при 100/125/150% DPI.

Критерий выхода: imported dataset всегда остаётся доступным, очистка не падает на удалённых
виджетах, а рабочая шапка занимает существенно меньше места без потери шкалы и единицы.

## Следующие этапы

- [ ] read-only offline WITSML 2.1 inventory и mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays в одной форме;
- [ ] directory watcher с preview-подтверждением ежедневного прироста;
- [ ] secured ETP 1.2 только после успешного fixture replay.
