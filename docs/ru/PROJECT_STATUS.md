# Статус проекта

Срез: 23 июля 2026 года. Версия: 0.7.43, тестовая сборка.

## Выполнено

- приветственное окно показывается не менее 3000 мс без блокирующего `sleep`, затем плавно исчезает за 180 мс;
- project format v18 и безопасная миграция v17 → v18;
- persisted acquisition schema v1 в `well.acquisition_sessions`;
- immutable index/curve schema и append-only `DATA_ROW`, `EVENT_UPSERT`, `EVENT_DELETE`;
- непрерывная sequence, bounded buffer и явный backpressure без потери records;
- атомарный rollback dataset/events/journal при ошибке;
- checkpoints с row count и dataset/events/audit SHA-256;
- deterministic replay с начала или после verified checkpoint;
- одинаковые rows, operational events, QC flags и report projection после replay;
- закрытая session с final checkpoint и final audit digest.

Целевой startup/version набор: 13 passed. Доступная headless-регрессия: 964 passed,
4 skipped, 3 deselected из-за отсутствующего `lasio`. Полный Qt/LAS/Ruff/mypy gate и
Windows/HiDPI/PDF/physical-print smoke-test остаются обязательными.

Следующий срез: versioned lag/depth correction без изменения append-only source.

См. [Acquisition replay](ACQUISITION_REPLAY.md) и [общий статус](../PROJECT_STATUS.md).
