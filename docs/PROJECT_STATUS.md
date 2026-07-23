# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.43, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline 0.7.28: Ruff чист, mypy — 0 ошибок
в 262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено. Для 0.7.43 выполнены
`compileall`, целевые startup timing-тесты и доступная headless-регрессия. Полный набор требует
`PySide6`, `pyqtgraph`, `lasio`, Ruff и mypy. Сборка остаётся тестовой до повторного полного gate
и Windows/HiDPI/PDF/physical-print smoke-test.

## Подтверждённая рабочая основа

- приветственное окно с неблокирующим минимальным временем видимости 3000 мс и fade-out 180 мс;
- project format v18 с безопасной цепочкой миграций v16 → v17 → v18;
- acquisition schema v1 и persisted `Well.acquisition_sessions`;
- immutable dataset schema для индексов, кривых, UOM и semantic metadata;
- append-only records `DATA_ROW`, `EVENT_UPSERT`, `EVENT_DELETE` с непрерывной sequence;
- bounded pending buffer с явным backpressure без потери records;
- атомарное применение записи с rollback dataset, events и journal;
- checkpoints с row count, dataset/events SHA-256 и combined audit digest;
- deterministic replay с начала или после проверенного checkpoint;
- совпадение replayed rows, typed events, QC flags и exact ReportDefinition projection;
- закрытая session с финальным checkpoint, canonical UTC timestamp и final audit digest;
- сохранён operational-event contract 0.7.41 и существующие ReportDefinition v2, Coverage v1,
  Passport v4 и output transaction v1.

## Результаты текущего среза

| Проверка | Результат |
|---|---|
| Startup splash | минимум 3000 мс от фактического show event, затем fade-out 180 мс |
| Source contract | append-only records, contiguous sequence, immutable dataset schema |
| Growing dataset | exact indexes/curves, append-only rows, `NaN` для missing sample |
| Buffer | bounded queue, explicit backpressure, ordered drain |
| Mutation | atomic row/event apply и rollback при ошибке |
| Checkpoint | row count + dataset/events/audit SHA-256 |
| Replay | с нуля или после verified checkpoint |
| Storage | `Well.acquisition_sessions`, project format v18 |
| Migration | v17 → v18 без изменения существующих datasets/events |
| Негативные сценарии | gap/duplicate sequence, schema mismatch, tampered checkpoint/projection |
| Целевой startup/version набор | 13 passed |
| Доступная headless-регрессия | 964 passed, 4 skipped, 3 deselected |

Три deselected-сценария требуют `lasio`; остальные недоступные collection-модули требуют
`PySide6`/`pyqtgraph`. Это ограничение окружения, а не подтверждение полного release gate.

## Технический долг с наибольшим риском

- повторить полный Ruff/mypy/Qt/LAS gate в установленном окружении;
- выполнить Windows/NTFS/network-share и physical-print smoke-test;
- добавить UI/import adapters поверх `AcquisitionController`, не обходя mutation boundary;
- определить versioned correction provenance и правила выбора source/corrected depth axis;
- после correction перейти к offline WITSML 2.1 inventory и fixture replay.

## Следующая контрольная точка

Следующий вертикальный срез — версионированная lag/depth correction. Критерий: исходная запись
остаётся неизменной, corrected axis имеет formula/version/provenance, а пользователь и отчёт явно
выбирают source или corrected projection.

Подробности: [Acquisition replay](ACQUISITION_REPLAY.md),
[Operational events](OPERATIONAL_EVENTS.md), [план](PROJECT_PLAN.md) и
[проверки](TESTING.md).
