# GEOLOG GASRATIO@Pixler 0.7.76 — WITS0 normalized batches и append-only AcquisitionSession

## Назначение среза

Версия 0.7.76 завершает этап D WITS0-интеграции. Подтверждённый Import Review теперь используется для преобразования типизированных WITS0 frames в immutable normalized measurement batches и для записи growing Dataset только через `AcquisitionController`.

## Нормализация WITS0

- `Wits0FrameNormalizer` использует immutable `Wits0ImportReviewCommit` и schema digest;
- WITS header date/time преобразуются в UTC Unix nanoseconds для `DATETIME` index;
- depth/time field index берётся только из выбранного `record/item`;
- отсутствующие значения кривых записываются как `None`, а затем как `NaN` в Dataset;
- неизвестное числовое vendor-поле может использовать подтверждённый numeric mapping;
- duplicate, invalid и out-of-order source sequence по умолчанию не создают строки;
- raw SHA-256, source record, source sequence, reception timestamp и raw reference входят в provenance batch/record;
- live и replay при одинаковых timestamps/source references создают одинаковые normalized batches.

## Bounded queue и backpressure

`AcquisitionController` получил атомарный `enqueue_many()` и `remaining_capacity`. Входящий batch либо полностью помещается в bounded queue, либо очередь не изменяется. `Wits0AcquisitionRuntime` поддерживает политики `RAISE` и `DRAIN_THEN_RETRY`, считает backpressure events и не нарушает непрерывную acquisition sequence.

## Checkpoints и controlled close

Runtime создаёт checkpoints по числу записанных records или времени, но только при пустой pending queue. Controlled close прекращает приём, полностью опустошает очередь, создаёт финальный checkpoint и переводит `AcquisitionSession` в `closed` с совпадающим final audit digest. Закрытая сессия проходит сохранение и повторное открытие проекта без миграции project format v20.

## Интерфейс

Окно **Файл → Захват WITS Level 0...** после актуального Import Review позволяет:

1. начать acquisition-сессию для текущей скважины;
2. видеть pending/applied/skipped/backpressure/checkpoint counters;
3. вручную записать bounded queue;
4. выполнить controlled close;
5. автоматически выбрать growing WITS0 Dataset в дереве проекта.

Сетевой socket остаётся в worker thread, а mutation проекта выполняется в GUI thread при polling immutable events.

## Проверка

Автоматические тесты покрывают time/depth index, sparse rows, unknown numeric fields, duplicate/out-of-order policy, live/replay equivalence, atomic batch enqueue, backpressure, checkpoint policy, controlled close и project round-trip. Полный GUI runtime требует Windows-окружение с PySide6/pyqtgraph и реальный anonymized GSWITS raw stream.

## Совместимость

Project format остаётся **v20**, form schema — **v8**, tablet layout — **v18**. Миграция существующих проектов не требуется. Возможности компактных колонок 50%, готовые ширины 48/80, все готовые и пользовательские формы, сохранение через Ctrl+S и повторное открытие остаются без изменений.
