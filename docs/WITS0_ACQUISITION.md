# WITS0 AcquisitionSession

## Назначение

Документ описывает этап после подтверждения **Import Review**. До запуска сессии приложение уже должно иметь immutable `Wits0ImportReviewCommit`, содержащий проверенную `AcquisitionDatasetSchema`, выбранный индекс и versioned custom profile.

## Конвейер

```text
Wits0ParsedFrame
    ↓ Wits0FrameNormalizer
Wits0MeasurementBatch
    ↓ bounded queue
AcquisitionRecord(DATA_ROW)
    ↓ AcquisitionController
append-only Dataset + AcquisitionSession
```

Raw `*.wits` не изменяется. Normalizer хранит SHA-256 исходного frame, `record/item`, source sequence, reception timestamp и raw reference.

## Индекс

Для `header:datetime` items 05 и 06 объединяются с явно подтверждённым timezone, переводятся в UTC и сохраняются как Unix nanoseconds. Для depth/time field index используется только выбранное поле. Frame без корректного индекса не создаёт строку.

## Значения каналов

Каждая строка содержит точный набор curve IDs из immutable schema. Присутствующее корректное число записывается как `float`; отсутствующее или повреждённое значение становится `None`, а в Dataset — `NaN`. Выбранное индексное поле не дублируется как curve.

## Sequence policy

Source sequence контролируется parser отдельно для каждого WITS record. По умолчанию duplicate, invalid и out-of-order frames пропускаются; gap допускается и остаётся в диагностике. Acquisition sequence не равна source sequence: она всегда начинается с 1 и непрерывна внутри `AcquisitionSession`.

## Bounded queue и backpressure

`AcquisitionController.enqueue_many()` сначала проверяет ёмкость, sequence, record IDs и schema всего batch. При любой ошибке pending queue не изменяется. Политика `RAISE` возвращает backpressure вызывающему коду; `DRAIN_THEN_RETRY` применяет часть pending records и повторяет enqueue один раз.

## Checkpoints

Checkpoint создаётся только при пустой pending queue. Runtime поддерживает порог по числу applied records и интервалу времени. Checkpoint фиксирует sequence, row count, Dataset digest, events digest и audit digest.

## Controlled close

Controlled close:

1. запрещает новые frames;
2. полностью опустошает pending queue;
3. создаёт финальный checkpoint;
4. устанавливает `closed_at`;
5. записывает final audit digest;
6. переводит session в `closed`.

После close новые records отклоняются. Сохранённый проект проходит повторное открытие и проверку append-only projection.

## Интерфейс оператора

В окне WITS0 доступны команды **Начать сессию**, **Записать очередь** и **Закрыть сессию**. Статус показывает pending records, applied rows, skipped frames, checkpoints и backpressure. Закрытие окна при активной сессии выполняет controlled close после остановки TCP worker и обработки оставшихся immutable events.

## Открытая полевая приёмка

Встроенный GeoScape mapping должен быть подтверждён реальным anonymized GSWITS raw stream. На Windows требуется проверить reconnect, длительную запись, заполнение диска, аварийное завершение, повторное открытие проекта и совпадение live/replay Dataset digests.
