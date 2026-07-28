# Захват и разбор WITS Level 0

## Стандартная шапка GeoScape GSWITS

Каталог GeoSensor `WITS.csv` подтверждает: `01` — Well Identifier, `02` — Sidetrack/Hole Section,
`03` — Record Identifier, `04` — Sequence Identifier, `05` — Date, `06` — Time, `07` — Activity Code.
Sequence QC использует item `04`; item `02` не является sequence number.

## Назначение

Команда **Файл → Захват WITS Level 0...** принимает поток GSWITS по TCP, сохраняет входные
байты без изменения и пропускает каждый полный пакет через типизированный parser. После
подтверждённого Import Review можно запустить append-only `AcquisitionSession`; raw-слой и parser
остаются неизменяемой границей, а Dataset изменяется только через `AcquisitionController`.

## Настройка TCP-сервера

Используйте этот режим, когда GSWITS настроен как **Исходящее соединение (TCP-клиент)**.

1. Выберите **Входящее соединение — TCP-сервер**.
2. Оставьте адрес `127.0.0.1` по умолчанию, если GSWITS работает на том же компьютере.
3. Для другого компьютера укажите IP конкретного доверенного интерфейса. `0.0.0.0` используйте
   только после явного решения в изолированной доверенной сети с firewall allowlist.
4. Укажите тот же порт, на который подключается GSWITS.
5. Выберите каталог raw-данных и нажмите **Запустить захват**.
6. В GSWITS сохраните настройки и проверьте состояние соединения.

WITS0 не имеет встроенных шифрования и аутентификации. Никогда не публикуйте listener в интернет
и не настраивайте router port forwarding.

## Настройка TCP-клиента

Используйте этот режим, когда GSWITS настроен как **Входящее соединение (TCP-сервер)**.

1. Выберите **Исходящее соединение — TCP-клиент**.
2. Укажите IP компьютера GSWITS и его порт.
3. Нажмите **Запустить захват**.
4. После разрыва Pixler повторяет подключение с ограниченной увеличивающейся задержкой.

## Что сохраняется

Каждое соединение получает отдельный каталог. Файлы `*.wits` содержат точные входные байты,
а `*.chunks.jsonl` фиксируют UTC-время, offset, размер TCP chunk и connection ID. Сегменты не
перезаписываются и пригодны для deterministic replay.

## Как работает parser

Один `Wits0StreamProcessor` используется для live TCP и replay. Конвейер выполняется в порядке:

```text
TCP chunk / raw chunk
        ↓
Wits0FrameDecoder: && ... !!
        ↓
Wits0Parser: record/item/raw value
        ↓
типизация по профилю
        ↓
Wits0SequenceTracker
        ↓
immutable Wits0ParsedFrame + diagnostics
```

Parser поддерживает `float`, `integer`, `text`, `date` и `time`. Стандартные items 01–07 — это
скважина, секция/боковой ствол, идентификатор записи, sequence number, дата, время и код работы.
Поля 08–99 сначала сопоставляются с проверенным профилем `geoscape-gswits.json`, затем с полным
каталогом `geosensor-wits-level0.json`; каталог не выдумывает UOM.

Повреждённая строка не отменяет пакет. Исходная строка, исходное значение, неизвестный
`record/item` и ошибка преобразования остаются в `Wits0ParsedFrame` и входят в детерминированный
снимок обнаружения для Import Review.

## Контроль sequence number

Последовательность контролируется отдельно для каждого номера записи. Возможные состояния:

- `first` — первая последовательность данного record;
- `contiguous` — получено ожидаемое следующее значение;
- `duplicate` — повтор последнего sequence number;
- `gap` — обнаружен пропуск;
- `out_of_order` — пришло более старое значение;
- `invalid` или `unavailable` — поле 04 повреждено либо отсутствует.

При reconnect создаётся новый stream processor, поэтому sequence state не переносится между
разными TCP-соединениями. Raw-файл можно повторно обработать тем же pipeline.

## Окно контроля

- **Последние пакеты** показывает исходные frames `&& ... !!`.
- **Разобранные поля** показывает record, sequence status, mnemonic, типизированное значение,
  единицу и диагностику.
- **Соединения и ошибки** показывает подключение, разрыв, raw-сегменты, parser warnings и errors.
- Панель состояния считает поля, parser warnings/errors и sequence anomalies.

Закрытие окна останавливает worker и закрывает файлы.

## Import Review

После приёма пакетов нажмите **Проверка импорта…**. Диалог работает с immutable snapshot и:

1. показывает каждый обнаруженный `record/item`, исходный mnemonic, тип, UOM, статистику и примеры;
2. предлагает semantic binding через Semantic Channel Dictionary;
3. позволяет выбрать WITS header datetime либо числовое поле глубины/времени как active index;
4. позволяет скрыть канал, изменить canonical mnemonic/kind, quantity class и UOM;
5. блокирует non-numeric curves, несовместимые quantity classes и требующийся численный UOM conversion;
6. одним атомарным действием создаёт immutable `AcquisitionDatasetSchema`;
7. сохраняет mapping отдельным versioned JSON-профилем, не меняя встроенный GeoScape profile.

Fingerprint описывает mapping surface, поэтому новые значения уже известных полей не отменяют
подтверждение. Новый `record/item`, изменение inferred type/UOM или появление нового index source
переводит схему в состояние **Устарело** и требует повторного Import Review. Кнопка
**Сбросить обнаружение** очищает только текущий snapshot и commit; сохранённые versioned profiles
на диске не удаляются.

## AcquisitionSession

После подтверждения схемы выберите текущую скважину и нажмите **Начать сессию**. Приложение:

1. преобразует принятые frames в immutable normalized measurement batches;
2. ставит записи в bounded queue атомарно, без частичного enqueue;
3. при backpressure применяет настроенную политику `DRAIN_THEN_RETRY`;
4. записывает строки только через `AcquisitionController`;
5. создаёт checkpoints только при пустой pending queue;
6. показывает pending, applied, skipped, checkpoints и backpressure;
7. по **Закрыть сессию** прекращает приём, опустошает очередь и создаёт финальный checkpoint.

Growing Dataset сразу выбирается в дереве проекта. **Записать очередь** вручную применяет все
ожидающие records. Закрытие окна при активной сессии сначала останавливает TCP worker, обрабатывает
оставшиеся immutable events и выполняет controlled close. Подробный контракт: [WITS0_ACQUISITION.md](WITS0_ACQUISITION.md).

## Ограничения

- профиль GeoScape основан на руководстве GSWITS и требует подтверждения реальным raw-потоком;
- неизвестные поля сохраняются и редактируются в Import Review, но требуют ручного подтверждения;
- численное UOM conversion пока не выполняется: source и canonical UOM должны разрешаться в одну каноническую единицу;
- WITS0-порт нельзя открывать в интернет; удалённый bind допустим только в изолированной
  доверенной сети с firewall allowlist;
- raw-файлы не заменяют сохранение проекта через **Ctrl+S**.
