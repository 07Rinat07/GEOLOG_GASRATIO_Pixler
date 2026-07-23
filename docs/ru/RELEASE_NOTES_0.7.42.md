# Примечания к выпуску 0.7.42 — append-only acquisition и replay

- добавлена persisted acquisition session с immutable dataset schema;
- строки и operational events записываются в непрерывный append-only journal;
- реализованы bounded buffer, backpressure, atomic rollback и controlled close;
- checkpoints подписывают row count, dataset/events и общий audit digest;
- replay с начала или после verified checkpoint транзакционно воспроизводит rows, events, QC и отчёт и проверяет metadata;
- project format повышен до v18 с безопасной миграцией v17 → v18;
- следующий этап — versioned lag/depth correction без изменения source journal.

Проверка: 127 focused tests passed; headless — 952 passed, 4 skipped, 3 deselected.
