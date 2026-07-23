# Append-only acquisition и детерминированный replay

Статус: реализовано в 0.7.42. Acquisition schema: v1. Project format: v18.

Записанный `AcquisitionSession` является первичным источником. Growing `Dataset` и
`operational_events` — проверяемые проекции, которые должны воспроизводиться с теми же строками,
событиями, QC и отчётом.

## Правила

- одна сессия фиксирует immutable schema индексов и кривых;
- records имеют непрерывную sequence и тип `DATA_ROW`, `EVENT_UPSERT` или `EVENT_DELETE`;
- строки только дописываются, missing curve value становится `NaN`;
- bounded buffer возвращает явный backpressure и ничего не отбрасывает;
- ошибка применения атомарно откатывает dataset, events и journal;
- checkpoint подписывает row count, dataset/events fingerprints и общий audit digest;
- replay выполняется на рабочей копии с начала либо после совпавшего checkpoint, проверяет metadata/fingerprints и commit-ится только целиком;
- закрытая сессия требует финальный checkpoint и совпавший final audit digest.

Project format v18 хранит сессии в `well.acquisition_sessions`. Миграция `v17 → v18` добавляет
пустую collection без изменения существующих данных. Следующий слой — версионированная
lag/depth correction, которая не меняет append-only source.
