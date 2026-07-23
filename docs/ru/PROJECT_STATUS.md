# Статус проекта

Срез: 23 июля 2026 года. Версия: 0.7.41, тестовая сборка.

## Выполнено

- шесть типизированных operational-event payload: drilling/gas/show/sample/casing/formation-top;
- общий envelope с depth/time anchors, UTC timestamps, source, revision и calibration;
- QC duplicate, out-of-order, gap, stale, calibration missing/expired;
- `OperationalEventController` как единственная изменяющая граница;
- project format v17 и безопасная миграция v16 → v17;
- строгий discriminator codec и round-trip typed payload;
- EVENTS/DRILLING используют точный интервал `ResolvedReportDefinition`;
- удалены устаревшие import-controller дубликаты из `ui`.

Расширенный целевой набор: 108 passed. Доступная headless-регрессия: 936 passed, 4 skipped.
Полный Qt/LAS/Ruff/mypy gate и Windows/HiDPI/PDF/physical-print
smoke-test остаются обязательными.

Следующий этап: append-only growing dataset, checkpoint и детерминированный replay.

См. [Operational events](OPERATIONAL_EVENTS.md) и [общий статус](../PROJECT_STATUS.md).
