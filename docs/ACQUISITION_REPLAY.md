# Append-only acquisition и deterministic replay

Статус: реализовано в версии 0.7.42. Acquisition schema: v1. Project format: v18.

## Назначение

Контракт хранит записанный поток как первичный append-only источник, а `Dataset` и
`Well.operational_events` — как проверяемую проекцию. Повторное воспроизведение того же журнала
обязано создавать те же строки, события, QC-флаги и отчётные данные.

## Состав контракта

`AcquisitionSession` связывает одну скважину и один growing dataset. Сессия содержит:

- immutable `AcquisitionDatasetSchema` с точным набором индексов и кривых;
- непрерывную sequence записей начиная с 1;
- `DATA_ROW`, `EVENT_UPSERT` и `EVENT_DELETE` records;
- checkpoints с row count и SHA-256 fingerprints dataset/event projections;
- состояние `open` или `closed`, canonical UTC close time и финальный audit digest.

Одна новая source session требует пустую event projection и пустой либо отсутствующий dataset.
Это исключает неявное смешивание записанного источника с ручными изменениями.

## Growing dataset

Каждая `DATA_ROW` запись обязана содержать точный набор index IDs и curve IDs из схемы.
Строки только дописываются. Пропущенное значение кривой хранится как `NaN`; отсутствующий канал
не допускается, потому что состав каналов закреплён схемой. DATETIME index принимает Unix
nanoseconds, остальные индексы — конечные числа.

## Buffer и backpressure

`AcquisitionController` использует ограниченную pending-очередь. При заполнении вызывающая
сторона получает `AcquisitionBackpressureError`; данные не отбрасываются и sequence не
продвигается. `drain()` применяет записи строго по порядку. Ошибка строки или события откатывает
Dataset, events и append-only journal к состоянию до записи.

## Checkpoint

Checkpoint разрешён только для открытой сессии и пустого pending buffer. Он фиксирует:

- последнюю применённую sequence;
- число строк dataset;
- dataset SHA-256;
- events SHA-256;
- audit SHA-256 от session ID, sequence и двух fingerprints.

Проверка checkpoint отклоняет любую подмену строк, curve state/version, событий, QC или порядка
источника. Закрытие сессии автоматически создаёт финальный checkpoint.

## Replay

`replay_acquisition_session()` поддерживает два режима:

1. replay с sequence 1 в чистую скважину;
2. продолжение после уже проверенного checkpoint.

Во время replay проверяются все checkpoints, встреченные в журнале. Dataset fingerprint включает
schema/metadata индексов и кривых, значения, curve version/state и выбранный active index. Для
закрытой source session финальный audit digest также должен совпасть. Replay выполняется на
рабочей копии и commit-ится только после полной проверки; divergence завершает операцию
`AcquisitionReplayError`, не меняя целевую проекцию частично.

## Хранение и миграция

Project format v18 добавляет `well.acquisition_sessions`. Миграция `v17 → v18` создаёт пустой
объект сессий и не изменяет datasets, operational events, interpretations или layouts.
Codec строго отклоняет неизвестные поля, неверный discriminator, разрывы sequence, повторные IDs,
несогласованную схему и повреждённые checkpoints.

## Ограничения текущего среза

- source session владеет одной dataset/event projection для скважины;
- live network transport, WITSML и ETP пока не входят в контракт;
- lag/depth correction будет отдельной версионированной производной проекцией и не изменит
  append-only source;
- UI adapters должны вызывать controller и не менять `Dataset`, events или session напрямую.
