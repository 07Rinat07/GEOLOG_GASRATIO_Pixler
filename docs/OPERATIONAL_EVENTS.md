# Типизированные operational events

Статус: event contract реализован в 0.7.41 и сохраняется в текущем project format v19.

Operational event — неизменяемая запись операции или геологического наблюдения, привязанная
к скважине и к глубине и/или времени. Контракт не зависит от Qt и используется одинаково
хранилищем проекта, QC, контроллером изменений и отчётным resolver.

## Типы событий

Поддерживаются шесть строгих discriminator-типов:

| `kind` | Payload |
|---|---|
| `drilling` | activity, ROP, RPM, WOB, hookload |
| `gas` | Total Gas, methane, ethane, propane, connection gas |
| `show` | show type, intensity 1–5, fluorescence colour, description |
| `sample` | sample code/type, bottom depth, description |
| `casing` | casing type, outer diameter, shoe depth, status |
| `formation_top` | formation code/name, confidence, description |

Payload другого типа отклоняется. Codec также отклоняет неизвестный discriminator,
неизвестные поля и несовпадение ключа словаря с `event_id`.

## Общий envelope

Каждое событие содержит:

- стабильные `event_id`, `well_id` и `kind`;
- один или несколько anchors: `depth_m`, `elapsed_time_s`, `measured_at`;
- `received_at` для acquisition-order и stale QC;
- `source`, положительный `revision` и typed payload;
- необязательные `calibration_id` и `calibrated_at`;
- рассчитанный tuple `qc_flags`.

ISO-8601 timestamps обязаны содержать часовой пояс и канонизируются в UTC с суффиксом `Z`.
Глубина и относительное время должны быть конечными неотрицательными числами.

## QC schema v1

`OperationalEventQcEvaluator` детерминированно пересчитывает полную коллекцию скважины:

- `duplicate` — совпадают kind, anchors и typed payload;
- `out_of_order` — received-order противоречит порядку основной координаты;
- `gap` — превышен policy-порог глубины или времени;
- `stale` — arrival delay превышает policy-порог;
- `calibration_missing` — для требующего калибровки типа нет calibration ID;
- `calibration_expired` — возраст калибровки превышает TTL.

Пороговые значения задаются immutable `OperationalEventQcPolicy`. По умолчанию calibration
обязательна для gas events. QC не зависит от порядка ключей JSON.

## Изменение данных

`OperationalEventController` — единственная изменяющая граница:

- create требует `revision=1` и уникальный ID;
- update использует optimistic `expected_revision` и увеличивает revision;
- remove может проверять revision;
- cross-well event и изменение `event_id` блокируются;
- после каждой операции QC пересчитывается для всей коллекции;
- list возвращает события в детерминированном порядке.

UI или import adapter должны вызывать controller, а не менять `Well.operational_events`
напрямую.

## Хранение в project format v19

События сохраняются в `well.operational_events` как объект `event_id → event`.
Миграция `v16 → v17` добавляет пустой объект в каждую скважину и не изменяет существующие
данные. JSON decoder восстанавливает конкретный payload-класс по discriminator и отклоняет
повреждённые или неоднозначные записи.

## ReportDefinition

`resolve_operational_event_report()` принимает уже готовый `ResolvedReportDefinition` и
использует его точные `start/end` без повторного вычисления строк:

- depth index использует `depth_m`;
- relative-time index использует `elapsed_time_s`;
- datetime index использует UTC `measured_at`;
- `DRILLING` section включает drilling events;
- `EVENTS` section включает все типы или фильтр `event_kinds`, например
  `(("event_kinds", "gas,show,formation_top"),)`.

События без anchor для выбранного индекса не подменяются другой координатой и не попадают в
результат.

## Связь с acquisition replay

Append-only growing dataset, checkpoints и deterministic replay реализованы в 0.7.42.
Operational events применяются через тот же revision/QC controller и воспроизводятся с тем же
events fingerprint. Следующий этап — versioned lag/depth correction без изменения source journal.
Подробнее: [Acquisition replay](ACQUISITION_REPLAY.md).
