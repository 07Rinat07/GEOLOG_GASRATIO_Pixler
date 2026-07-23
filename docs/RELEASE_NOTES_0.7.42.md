# 0.7.42 — append-only acquisition and deterministic replay

Test build. Project format: v18. Acquisition schema: v1.

## Русский

- добавлен persisted `AcquisitionSession` как первичный append-only источник growing dataset;
- введены immutable schema индексов/кривых и records `DATA_ROW`, `EVENT_UPSERT`, `EVENT_DELETE`;
- реализованы непрерывная sequence, bounded buffer, явный backpressure и ordered drain;
- каждая запись применяется атомарно с rollback dataset, operational events и source journal;
- checkpoints фиксируют row count, dataset/events SHA-256 и combined audit digest;
- deterministic replay работает с начала либо после verified checkpoint, проверяет metadata и все fingerprints и commit-ится транзакционно;
- controlled close сохраняет final checkpoint, canonical UTC timestamp и final audit digest;
- project format повышен до v18; миграция v17 → v18 добавляет пустой `acquisition_sessions`;
- replay подтверждён на одинаковых rows, typed events, QC flags и ReportDefinition projection;
- обновлены план, статус, архитектура, требования, testing gate и инструкции RU/KK/EN.

## Қазақша

- persisted `AcquisitionSession` growing dataset үшін primary append-only source ретінде қосылды;
- immutable index/curve schema және `DATA_ROW`, `EVENT_UPSERT`, `EVENT_DELETE` records енгізілді;
- үздіксіз sequence, bounded buffer, нақты backpressure және ordered drain іске асырылды;
- әр record dataset, operational events және source journal rollback-пен атомарлы қолданылады;
- checkpoints row count, dataset/events SHA-256 және combined audit digest сақтайды;
- deterministic replay нөлден немесе verified checkpoint-тен жалғасып, metadata мен барлық fingerprints тексереді және транзакциялық commit жасайды;
- project format v18-ге көтерілді, v17 → v18 migration бос `acquisition_sessions` қосады;
- replay бірдей rows, typed events, QC flags және ReportDefinition projection беретіні тексерілді.

## English

- added persisted `AcquisitionSession` as the primary append-only source for a growing dataset;
- added immutable index/curve schemas and `DATA_ROW`, `EVENT_UPSERT`, and `EVENT_DELETE` records;
- implemented contiguous sequencing, bounded buffering, explicit backpressure, and ordered drain;
- each record applies atomically with dataset, operational-event, and source-journal rollback;
- checkpoints capture row count, dataset/events SHA-256, and a combined audit digest;
- deterministic replay starts from zero or resumes after a verified checkpoint, validates metadata and all fingerprints, and commits transactionally;
- controlled close stores a final checkpoint, canonical UTC timestamp, and final audit digest;
- upgraded project format to v18 with a safe v17 → v18 empty-session migration;
- verified identical rows, typed events, QC flags, and ReportDefinition projection after replay.

## Verification

- expanded focused set: 127 passed;
- available headless regression: 952 passed, 4 skipped, 3 deselected;
- full Qt/LAS/Ruff/mypy gate remains mandatory in an installed environment.
