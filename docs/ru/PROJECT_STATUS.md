## Завершено в 0.7.83: совместимость GeoScape WITS

Исправлены header items 01–07 и sequence item 04, добавлен каталог 963 полей records 1–25,
воспроизводимый generator, хеши reference-файлов и regression tests на реальном примере руководства.
Vendor binaries и базы остаются внешними и не распространяются.

## Завершено в 0.7.82: ETP ChannelData AcquisitionSession

Завершены устойчивый по URI Import Review, нормализованные measurement batches и append-only запись с дедупликацией перекрытия после reconnect.

# Состояние проекта

## Завершено в 0.7.81: основа клиента WITSML 2.x / ETP 1.2

Реализованы защищённый WSS transport, RequestSession/OpenSession negotiation, read-only Discovery,
Store и Data Array, Channel Streaming/Channel Subscribe, correlation, multipart FIN, automatic ACK и
восстановление подписок после reconnect. Credentials и audit отделены от project file. Открыты
реальная Avro interoperability с ETP server и Windows Qt-приёмка.

## В разработке: полевая приёмка WITS0

Программные этапы raw capture, parser, Import Review, append-only `AcquisitionSession`, live monitor
и reliability завершены. Реализованы connection records, disk guard, raw retention, restart
recovery, workspace persistence и Windows soak-test tooling. Остаются реальный 8–24-часовой GSWITS
soak, контролируемый low-space/disk-full тест, independent channel scales, Windows startup/service
strategy и подписанный полевой checklist. Встроенный GeoScape mapping требуется подтвердить
реальным anonymized raw-потоком.

## Завершено в 0.7.79: офлайн-импорт WITSML 2.x

Безопасный inventory расширен чтением embedded/relative-file `ChannelData`, выбором ChannelSet,
активного time/depth index и scalar numeric каналов. Import Review выполняет semantic mapping,
строгое UOM conversion, QC строк и атомарно создаёт Dataset с source/data SHA-256 и стабильным
digest. Binary Avro, multidimensional arrays, SOAP и ETP остаются последующими этапами.

## Завершено в 0.7.80: WITSML 1.4.1.1 SOAP только для чтения

Добавлены GetVersion, GetCap и read-only GetFromStore, просмотр Well → Wellbore → Log → LogData,
тайм-ауты, bounded retry, hash-chained audit и хранение пароля в Windows Credential Manager.
Удалённый LogData проходит существующие Import Review и атомарную регистрацию Dataset. Add,
Update и Delete запрещены на уровне клиента.

## В разработке: GeoScape II GS2

Добавлены безопасная проверка контейнера, выбор внутренней таблицы и её импорт через существующий
Paradox reader, Import Review и `Dataset`. На образце СГ-8 распознаны 13 таблиц Paradox 7.x;
`GS2#101.db` содержит TIME, DEPTH и 206 каналов на сетке 0,2 м. Пять частей `GS2#1…GS2#1_4`
автоматически объединяются в проверенную TIME-серию из 4 338 103 строк. `GS2.mdb` читается через
read-only Qt ODBC/ACE: импорт получает `WELLS`, формулы `RESGID → S-код`, Sensors fallback и
аудит. Отсутствие драйвера не блокирует импорт и сопровождается конкретной диагностикой.



## Завершено в 0.7.78

Добавлены stable connection IDs, append-only fsync JSONL lifecycle journal и типизированные
connection/disconnection acquisition records. Capture worker получил pre-write disk-space guard,
retention неактивных raw-сегментов и atomic recovery manifest. Startup безопасно исправляет
обрезанный chunk-index sidecar, а открытая WITS0-сессия восстанавливается по immutable schema и
versioned custom profile. Live workspace сохраняется per well. Добавлены Python/PowerShell Windows
soak tools с JSON-отчётом.

Срез: 27 июля 2026 года. Версия пакета: **0.7.78**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Завершено в 0.7.77

Добавлен read-only `AcquisitionLiveView`: current values, time/depth axes, auto-follow, pause-view,
history/downsampling и source/axis/invalid/missing markers поверх growing Dataset. Пауза
представления не останавливает acquisition.

Срез: 27 июля 2026 года. Версия пакета: **0.7.77**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Завершено в 0.7.76

Добавлены `Wits0FrameNormalizer`, immutable normalized measurement batches и
`Wits0AcquisitionRuntime`. Подтверждённые frames проходят через атомарный bounded enqueue,
backpressure policy, checkpoints и controlled close в append-only `AcquisitionSession`.
Окно WITS0 запускает сессию для текущей скважины, показывает pending/applied/skipped counters и
выбирает growing Dataset. Live/replay batches детерминированы, закрытая сессия проходит project
save/reopen без изменения project format.

Срез: 27 июля 2026 года. Версия пакета: **0.7.76**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Завершено в 0.7.75

Добавлен WITS0 Import Review: immutable discovery snapshot, таблица всех record/item,
Semantic Channel Dictionary, исходные и канонические UOM, выбор time/depth index,
hide/rename/manual override, versioned custom profile и атомарный commit immutable
`AcquisitionDatasetSchema`. Новые или изменённые record/item делают подтверждённую схему
устаревшей без изменения raw/parser данных.

Срез: 27 июля 2026 года. Версия пакета: **0.7.75**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Завершено в 0.7.74

Добавлены типизированный WITS0 parser, immutable parsed models, diagnostics и sequence tracking
по каждому record. Live TCP и replay используют один pipeline; окно захвата показывает parsed
fields и anomalies. Dataset commit остаётся следующим этапом.

Срез: 27 июля 2026 года. Версия пакета: **0.7.74**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Завершено в 0.7.73

Добавлены Qt-независимый WITS0 source adapter и окно **«Захват WITS Level 0»**. Сетевой worker
не блокирует GUI; raw bytes сохраняются раньше framing, а UI queue не влияет на raw. TCP chunks
индексируются по UTC/offset/size, live и replay используют один decoder. Dataset ещё не создаётся.

Срез: 27 июля 2026 года. Версия пакета: **0.7.73**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Завершено в 0.7.72

Верхние командные строки вынесены из native toolbar-area в центральный responsive host, а
минимальный размер окна ограничен рабочей областью активного монитора. Значки сохраняют
геометрию до `0,01` логического пикселя, отрисовываются минимум в один device pixel и получают
отдельную рамку выбора/перемещения. CSV/XLSX используют точные строки активного числового
DEPTH/TIME-индекса. Автоматические проверки выполнены; ручная Windows
external-monitor/HiDPI/physical-print приёмка остаётся открытой.

Срез: 27 июля 2026 года. Версия пакета: **0.7.72**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Завершено в 0.7.71

Обе верхние панели жёстко ограничены шириной окна и повторно адаптируются после F4, изменения команд, DPI и смены монитора. Значки справочника реально сужаются до 1×1 логического пикселя; обычные аннотации сохраняют минимум 40×24 px.

Срез: 25 июля 2026 года. Версия пакета: **0.7.71**. Project format: **v20**, form schema: **v8**, tablet layout: **v18**.

## Завершено в 0.7.70

- верхняя и F4-панель переведены на один ограниченный адаптивный ряд без системного overflow Qt;
- правый переключатель редактирования гарантированно остаётся внутри окна;
- значки справочника сжимаются независимо до 2 логических пикселей и сохраняют размер после Ctrl+S/повторного открытия.


Срез: 25 июля 2026 года. Версия пакета: **0.7.70**. Project format: **v20**,
form schema: **v8**, tablet layout: **v18**.

## Завершено в 0.7.69

- верхняя панель выбирает расширенный, компактный или сверхкомпактный режим по фактически
  измеренной ширине локализованных кнопок в логических пикселях Qt;
- фиксированный порог разрешения удалён: расчёт учитывает системный шрифт, стиль и текущий DPI;
- если даже режим значков не помещается, второстепенные команды переносятся в меню **«⋯»**;
- правый переключатель **«Редактирование формы»** не входит в список скрываемых команд и остаётся
  внутри доступной ширины панели;
- пересчёт выполняется при изменении окна, шрифта, темы, DPI, геометрии/рабочей области экрана и
  при переносе окна между ноутбуком и внешним монитором;
- после смены монитора выполняются немедленная и отложенная проверки метрик Windows;
- пользовательская документация, release notes и регрессионные тесты синхронизированы на RU/KK/EN.

## Сохранено из 0.7.68

- значки справочника свободно растягиваются по ширине и высоте;
- боковые маркеры меняют одну ось, угловые — обе оси, **Shift** сохраняет пропорции;
- обычные изображения не искажаются;
- ширина и высота участвуют в Undo/Redo, сохраняются через **Ctrl+S**, восстанавливаются после
  повторного открытия и одинаково используются на экране, в preview, PDF и печати.

## Сохранено из предыдущих версий

Компактные 44 px шапки без дублирующей надписи **«Шкала»**, уменьшенные геологические колонки,
единый полный каталог готовых, **18 заводских** и пользовательских форм, полное окно создания и
сохранения формы, а также команда **«Сбросить данные диагностики…»** остаются без изменения.

## Совместимость

Формат проекта, схема формы и tablet layout не изменялись. Миграция существующих проектов и форм
не требуется. Корневой `README.md` остаётся кратким и не содержит подробностей исправления.
