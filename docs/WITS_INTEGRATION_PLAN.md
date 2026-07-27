# Обновлённый план интеграции WITS0 и WITSML

Актуально на 27 июля 2026 года. Документ объединяет существующий append-only acquisition-контракт,
офлайн-инвентарь WITSML 2.x, руководство GSWITS GeoScape и практический план разработки
real-time рабочего места ГТИ.

## 1. Цель

GEOLOG GASRATIO@Pixler должен принимать исторические и потоковые данные из разных источников,
приводить их к одной проверяемой модели и отображать одинаковыми инструментами независимо от
формата источника:

```text
WITS0 TCP / WITS0 raw / GS2 / LAS / CSV / Excel / WITSML XML/EPC / SOAP / ETP
                                ↓
                     Source adapters and raw layer
                                ↓
                   Parser, profile and normalization
                                ↓
                  Append-only AcquisitionSession
                                ↓
          Dataset, QC, live values, tablet, reports and replay
```

Основной принцип: сырой поток сохраняется раньше семантического разбора. Ошибка профиля,
неизвестный канал или временная недоступность Dataset не должны приводить к потере исходных байтов.

## 2. Подтверждённая точка интеграции GeoScape

Руководство GSWITS подтверждает два режима WITS-соединения:

1. GSWITS работает как TCP-клиент, а Pixler принимает входящее соединение как TCP-сервер.
2. GSWITS работает как TCP-сервер, а Pixler подключается к нему как TCP-клиент.

Порты `4150` и `2041` на изображениях руководства являются примерами конфигурации, поэтому IP и
порт остаются пользовательскими настройками. Пакеты ограничены маркерами `&&` и `!!`; TCP не
сохраняет границы пакетов, следовательно отдельный incremental frame decoder обязателен.

Руководство описывает записи 1, 2, 3, 6, 7, 8, 11, 12, 13, 14 и 17. Их поля перенесены в
машинно-читаемый профиль `geoscape-gswits.json`, но окончательное соответствие должно быть
подтверждено реальным raw-дампом конкретного комплекса.

## 3. Текущая реализованная база

### 3.1. Append-only acquisition

Уже реализованы:

- immutable `AcquisitionDatasetSchema`;
- последовательные `AcquisitionRecord`;
- bounded buffer и backpressure;
- атомарное добавление строк и событий;
- checkpoints и SHA-256 fingerprints;
- controlled close;
- deterministic replay;
- отдельная versioned lag/depth correction без изменения source.

### 3.2. WITSML

Уже реализован безопасный read-only inventory WITSML 2.x для XML, WITSML, ZIP и EPC:

- top-level objects;
- `schemaVersion`, UUID, references;
- `Channel` mnemonic, data type, UOM, source, class, indexes and range;
- ресурсные лимиты и защита XML/ZIP.

Пока не реализованы channel arrays, mapping в Dataset, SOAP и ETP.

### 3.3. WITS0 capture, parser, Import Review, AcquisitionSession и Live UI — срезы 0.7.73–0.7.77

Реализованы:

- TCP server и TCP client;
- автоматическое переподключение клиента с bounded exponential delay;
- incremental `&& ... !!` frame decoder;
- ограничение максимального размера незавершённого пакета;
- append-only raw segments;
- JSONL sidecar с UTC-временем получения, offset и размером каждого TCP chunk;
- отдельный worker thread, не блокирующий Qt GUI;
- modeless окно состояния, raw-пакетов и ошибок;
- replay raw-файла через тот же `Wits0StreamProcessor`;
- встроенный профиль GeoScape GSWITS: 11 записей и 105 vendor fields;
- immutable `Wits0ParsedFrame` и `Wits0ParsedField`;
- типы `float`, `integer`, `text`, `date`, `time`;
- сохранение исходной строки и raw reference;
- диагностика unknown record/item, duplicate field, invalid line/value и NaN/Inf;
- sequence tracking отдельно по каждому record: first/contiguous/duplicate/gap/out-of-order;
- один framing/parsing/sequence pipeline для live TCP и replay;
- вкладка разобранных полей и parser counters в modeless monitor;
- immutable discovery snapshot всех обнаруженных data record/item;
- детерминированный fingerprint mapping surface, не меняющийся от новых значений тех же полей;
- Semantic Channel Dictionary binding и явные source/canonical UOM;
- выбор WITS header datetime или numeric depth/time field как active index;
- hide/rename/manual semantic override;
- versioned custom mapping profiles без изменения встроенного GeoScape profile;
- атомарный commit immutable `AcquisitionDatasetSchema`;
- stale-state при появлении нового или изменённого record/item после подтверждения;
- deterministic normalized measurement batches и bounded append-only runtime;
- current values с quality state;
- read-only time/depth axes, auto-follow, pause-view и history window;
- peak-preserving downsampling и markers для sequence/axis/missing/invalid gaps.

Срезы 0.7.76–0.7.77 добавили normalized batches, append-only `AcquisitionSession`,
current values и live/history time/depth visualization. Численное UOM conversion по-прежнему
не выполняется молча: разные совместимые единицы блокируются до отдельного conversion-слоя.

## 4. Целевая архитектура

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Source adapters                                                     │
├──────────────┬──────────────┬────────────┬──────────────┬────────────┤
│ WITS0 TCP    │ WITS0 replay │ GS2/LAS   │ WITSML XML   │ SOAP/ETP   │
│ client/server│ raw files    │ CSV/Excel │ ZIP/EPC      │ later      │
└──────┬───────┴──────┬───────┴─────┬──────┴──────┬───────┴─────┬──────┘
       │              │             │             │             │
       ▼              ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Raw boundary                                                        │
│ bytes, connection ID, arrival UTC, peer, segment, chunk offsets     │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Framing and protocol parser                                         │
│ WITS0 frame → record/item/value; WITSML object/channel/data arrays  │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Mapping and normalization                                           │
│ profile → semantic binding → explicit UOM → QC → Import Review      │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Append-only AcquisitionSession                                      │
│ records, checkpoints, Dataset projection, events, replay            │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ UI and reports                                                      │
│ current values, time/depth graphs, tablet, events, export, alarms   │
└─────────────────────────────────────────────────────────────────────┘
```

## 5. Контракты слоёв

### 5.1. Raw boundary

Raw-слой отвечает только за:

- подключение;
- получение байтов;
- UTC arrival time;
- сохранение без изменения;
- segment rotation;
- connection/disconnection journal;
- resource limits.

Он не определяет WITS record, mnemonic, единицу или индекс и не изменяет проект.

### 5.2. Frame decoder

Frame decoder преобразует произвольные TCP chunks в полные пакеты. Он должен одинаково работать
при live TCP и replay, включая:

- marker, разделённый между chunks;
- несколько frames в одном chunk;
- мусор до `&&`;
- незавершённый frame;
- oversized frame;
- разрыв соединения в середине frame.

### 5.3. Protocol parser

Следующий parser slice преобразует frame в immutable структуру:

```text
Wits0Frame
├── received_at_utc
├── raw_reference
├── record_no
├── sequence_no, если доступен
└── fields
    ├── item_no
    ├── raw_value
    ├── parsed_value
    └── parse_error
```

Повреждение одной строки не должно отменять сохранение frame или остальных полей.

### 5.4. Profile and mapping

Профиль не является доказательством данных. Он задаёт ожидаемое соответствие:

- record/item;
- canonical mnemonic;
- vendor name;
- source UOM;
- data type;
- exact/average/minimum/maximum;
- time/depth/depth-lagged/event index type;
- send policy.

Неизвестные record/item сохраняются и показываются в Import Review. Пользовательские overrides
сохраняются как отдельная версия профиля, а встроенный профиль не изменяется.

### 5.5. Dataset commit

Создание growing Dataset выполняется только после подтверждения:

- скважины и ствола;
- active index;
- набора каналов;
- semantic bindings;
- UOM conversions;
- NULL policy;
- duplicate/out-of-order policy.

После начала `AcquisitionSession` schema неизменна. Изменение состава каналов создаёт новую session
или контролируемую schema transition в будущем отдельном контракте.

## 6. Поэтапный roadmap

### Этап A — WITS0 raw capture — реализован в 0.7.73

- [x] TCP server;
- [x] TCP client;
- [x] client reconnect;
- [x] worker thread;
- [x] raw binary segments;
- [x] JSONL chunk index;
- [x] frame decoder;
- [x] replay iterator;
- [x] modeless monitor;
- [x] GeoScape GSWITS profile schema v1.

Оставшаяся полевая приёмка:

- [ ] проверить оба режима с реальным GSWITS;
- [ ] получить минимум 5–10 минут raw-потока;
- [ ] проверить бурение, газ, ёмкости и разрыв соединения;
- [ ] подтвердить кодировку и line endings;
- [ ] проверить длительную запись и ротацию файлов на Windows.

### Этап B — WITS0 parser and diagnostics — реализован в 0.7.74

- [x] parse record/item/value без зависимости от GUI;
- [x] сохранить исходную строку и raw reference;
- [x] поддержать отсутствие пробела между ID и значением;
- [x] определить single-record и mixed-record frames;
- [x] фиксировать unknown records/items и duplicate fields;
- [x] типизировать float/integer/text/date/time;
- [x] валидировать пустое значение, malformed number и NaN/Inf;
- [x] контролировать sequence number отдельно по каждому record;
- [x] диагностировать duplicate/gap/out-of-order/missing/invalid sequence;
- [x] использовать один `Wits0StreamProcessor` для live и replay;
- [x] доказать равенство live/replay output тестами с разными chunk boundaries;
- [x] показать разобранные поля и diagnostics в окне захвата.

Полевая приёмка parser остаётся открытой до получения реального anonymized raw-потока.

### Этап C — Import Review and schema creation — реализован в 0.7.75

- [x] показать все обнаруженные channels и sample/statistics snapshot;
- [x] сопоставить их с Semantic Channel Dictionary;
- [x] определить source and canonical UOM без молчаливого conversion;
- [x] выбрать WITS header datetime или numeric time/depth index;
- [x] разрешить hide/rename/manual semantic override;
- [x] сохранить versioned custom profile через exclusive-create;
- [x] сформировать immutable `AcquisitionDatasetSchema`;
- [x] выполнить atomic confirmation before session start;
- [x] использовать один discovery contract для live/replay;
- [x] помечать schema stale только при изменении mapping surface, а не при новых значениях уже известных fields.

Полевая приёмка mapping остаётся открытой до получения реального anonymized raw-потока.
Численное преобразование совместимых UOM вынесено в следующий отдельный normalization slice.

### Этап D — Live AcquisitionSession — реализован в 0.7.76

- [x] WITS frame → deterministic immutable normalized measurement batch;
- [x] append records through `AcquisitionController` only;
- [x] atomic bounded ingest queue and explicit `RAISE` / `DRAIN_THEN_RETRY` backpressure;
- [x] checkpoint policy by applied-record threshold or elapsed time on an empty queue;
- [x] controlled close with final checkpoint and audit digest;
- [x] raw SHA-256, record/source sequence, reception timestamp and raw-reference provenance;
- [x] resume of a persisted open session with continuous acquisition sequence;
- [ ] reconnect gaps and connection events as explicit acquisition records;
- [ ] start-new-session policy after a previous session for the same well is closed.

### Этап E — Live UI — основной срез реализован в 0.7.77

- [x] current values table с последним finite value и явным quality state;
- [x] time graph по реальному time index или read-only UTC `received_at` axis;
- [x] depth graph по реальному depth index или semantic depth curve;
- [x] auto-follow и pause-view без остановки acquisition;
- [x] history window и peak-preserving downsampling с сохранением NaN-разрывов;
- [x] quality/gap markers для source sequence, axis intervals, invalid и missing spans;
- [x] выбор отображаемых каналов в live monitor;
- [ ] connection/disconnection events как отдельные acquisition records;
- [ ] selected channels, axis mode и ranges сохраняются в workspace settings;
- [ ] отдельные дорожки/масштабы для каналов с несовместимыми единицами.

### Этап F — Reliability gate

- [ ] disk free-space checks;
- [ ] configurable raw retention and rotation;
- [ ] disk spool when Dataset commit is unavailable;
- [x] parser-level duplicate and out-of-order sequence detection;
- [x] parser-level sequence-gap detection for item 02;
- [ ] restart recovery for incomplete sessions;
- [ ] long-running soak test;
- [ ] Windows startup/service strategy evaluated separately;
- [ ] signed field smoke checklist.

### Этап G — WITSML offline data import

- [ ] ChannelSet and Channel selection;
- [ ] data arrays;
- [ ] time/depth index selection;
- [ ] Well/Wellbore binding;
- [ ] UOM normalization;
- [ ] Import Review;
- [ ] atomic Dataset creation;
- [ ] official or licensed fixtures with clear provenance.

### Этап H — WITSML 1.4.1.1 SOAP read-only

- [ ] `WMLS_GetVersion`;
- [ ] `WMLS_GetCap`;
- [ ] Well → Wellbore → Log → LogCurveInfo → LogData;
- [ ] read-only credentials outside project files;
- [ ] retry, timeout and audit;
- [ ] no Add/Update/Delete in the first slice.

### Этап I — WITSML 2.x / ETP 1.2

- [ ] secured WebSocket session;
- [ ] protocol negotiation;
- [ ] Discovery and Store;
- [ ] Data Array;
- [ ] Channel Streaming;
- [ ] correlation and acknowledgements;
- [ ] subscription recovery;
- [ ] credentials outside project files;
- [ ] same normalized `MeasurementBatch` boundary as WITS0.

### Этап J — Rules, alarms and structured MudLog views

- [ ] threshold, hysteresis and debounce;
- [ ] acknowledgement and audit;
- [ ] explicit quality and unavailable-channel state;
- [ ] gas/chromatograph views;
- [ ] drilling trends;
- [ ] pit/flow trends;
- [ ] decision-support wording only, without well-control certification claims.

## 7. Приоритет каналов GeoScape

Первый parser/mapping slice должен начать с записей:

1. record 1 — time-based drilling and total gas;
2. record 2 — depth-based drilling;
3. record 11 — pit volumes;
4. record 12 — chromatograph by time;
5. record 13 — chromatograph by lagged depth;
6. record 14 — lagged mud and total gas.

Record 3, 6, 7, 8 and 17 подключаются после стабильной основной линии.

## 8. Данные, необходимые от реального комплекса

Для завершения parser profile нужны:

- screenshot сетевых настроек GSWITS;
- выбранный client/server mode;
- фактический IP и порт;
- список включённых records;
- интервалы seconds/metres;
- 5–10 минут raw при обычном бурении;
- фрагмент с изменением глубины;
- фрагмент chromatograph/gas;
- фрагмент pit-volume changes;
- разрыв и повторное подключение;
- список дополнительных пользовательских полей, если они включены.

## 9. Нефункциональные требования

- GUI не выполняет blocking socket I/O.
- Raw bytes не отбрасываются из-за переполнения UI event queue.
- Source files не перезаписываются.
- Неизвестная UOM не конвертируется молча.
- WITS0-порт не публикуется напрямую в интернет.
- External credentials не сохраняются в project JSON.
- Live и replay одного raw-файла должны давать одинаковый parser output.
- Dataset изменяется только через application/domain controller boundary.
- Программа является decision-support tool и не заменяет решения персонала ГТИ и буровой.

## 10. Критерий первой полевой версии

Первая полевая версия считается готовой, когда она:

1. без потерь принимает WITS0 через оба TCP-режима;
2. восстанавливается после разрыва;
3. сохраняет проверяемый raw-поток;
4. deterministic replay воспроизводит тот же parser output;
5. подтверждённо разбирает основные записи GeoScape;
6. создаёт append-only AcquisitionSession через Import Review;
7. показывает текущие значения и time/depth graphs;
8. сохраняет gaps, unknown fields, QC и provenance;
9. проходит длительный Windows soak test;
10. не заявляет неподтверждённую промышленную сертификацию.
