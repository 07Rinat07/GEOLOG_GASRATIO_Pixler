# Проверка качества

Актуально на 24 июля 2026 года. Этот файл задаёт один действующий release gate. История
проверок отдельных версий хранится в release notes и не является текущей инструкцией.

## Автоматический gate

Запускать из корня проекта в установленном Windows-окружении:

```powershell
.venv\Scripts\python.exe -B -m ruff check src tests
.venv\Scripts\python.exe -B -m mypy src
.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

Требования:

- каждая команда завершается с кодом 0;
- pytest не допускает skipped обязательных сценариев, зависания или аварийного завершения;
- тесты не создают изменённые проектные/LAS-файлы в рабочем дереве;
- выборочный успешный набор не заменяет полный прогон.

Последний полностью подтверждённый baseline 0.7.28: Ruff — 0 ошибок; mypy — 0 ошибок
в 262 исходных файлах; полный pytest — 1217 пройдено и 10 пропущено, код завершения 0.

Для hotfix 0.7.46 в текущем контейнере выполнены `compileall`, focused import/recovery/
diagnostics набор — 76 passed, и доступная headless-регрессия — 1011 passed, 4 skipped,
3 deselected. Три deselected-сценария требуют отсутствующий `lasio`; Qt/LAS collection-модули
требуют `PySide6`, `pyqtgraph` или `lasio`. Ruff и mypy в контейнере также отсутствуют.
Это не заменяет полный gate. Перед stable команды выше и Windows/HiDPI/PDF/physical-print
smoke-test необходимо повторить в установленном окружении.

## Восстановление импорта LAS и диагностика

Обязательные проверки 0.7.46:

- grid overlay передаёт `Qt.MouseButton.NoButton`, а не обычное целое значение;
- исключение overlay не прерывает регистрацию dataset и включает безопасный grid fallback;
- исключение первого tablet render открывает LAS table recovery и сохраняет imported dataset;
- Import Review warnings видимы, но не блокируют подтверждение;
- ошибки чтения, parse, policy, review, registration и presentation получают точный stage;
- blocking report атомарно сохраняется, а UI поддерживает Copy/Save;
- duplicate mnemonics читаются по физическому столбцу;
- повреждение одного канала создаёт warning и не отклоняет остальные каналы;
- fixture 9847 строк / 73 канала проходит review без ошибок и создаёт bounded default layout;
- реальный проблемный LAS проходит Windows/PySide6 smoke-test без чёрного рабочего окна.

## Приветственное окно запуска

Для startup splash обязательны проверки:

- default minimum visibility равна 3000 мс;
- оставшаяся задержка уменьшается на фактически прошедшее время и не бывает отрицательной;
- значения `bool`, float, строка и `None` не принимаются как миллисекунды;
- отрицательные minimum/elapsed значения отклоняются;
- Qt-интеграция запускает отсчёт от фактического `showEvent`, не блокирует event loop и
  сохраняет fade-out 180 мс;
- если инициализация уже заняла не менее трёх секунд, fade начинается без дополнительной паузы.

## Semantic Channel Dictionary

Для семантической границы обязательны отдельные headless-проверки:

- точное, alias и legacy `S/GID` сопоставление через Sensors-каталог;
- сохранение исходной мнемоники, source UOM, confidence и evidence;
- явный unresolved для неизвестного vendor-канала или UOM;
- UOM quantity conflict как ошибка Import Review;
- round-trip project format v20 и миграции v15 → v16 → v17 → v18 → v19 → v20;
- сохранение binding при copy/merge/resample/TIME↔DEPTH;
- read-only гарантия `build_import_review()`;
- plan/preview/commit на глубокой копии без изменения loader-owned dataset;
- ручные index, NULL, channel, canonical, quantity и UOM overrides;
- блокировка commit при ошибках индекса или отсутствии импортируемых каналов;
- отмена CSV/Excel/LAS/Paradox до project-session port;
- одинаковый набор Import Review localization keys в RU/KK/EN.

## Operational events

Для operational-event schema v1 в текущем project format v20 обязательны проверки:

- все шесть discriminator-типов принимают только собственный typed payload;
- событие требует depth, elapsed-time или timezone-aware measurement timestamp;
- timestamps канонизируются в UTC и сохраняются при round-trip;
- codec отклоняет unknown kind/field, payload mismatch, cross-well ID и key/event_id mismatch;
- миграция v16 → v17 добавляет пустую collection и не изменяет исходный payload;
- duplicate, out-of-order, gap, stale и calibration flags не зависят от порядка JSON keys;
- controller блокирует duplicate ID, cross-well mutation и stale expected revision;
- update увеличивает revision, remove поддерживает revision guard;
- depth, relative-time и datetime EVENTS/DRILLING используют exact resolved bounds;
- event без anchor выбранного индекса не подменяется другой координатой.

## Append-only acquisition и replay

Для acquisition schema v1 в текущем project format v20 обязательны проверки:

- dataset schema фиксирует точные index/curve IDs, metadata и active index;
- records имеют уникальные IDs и непрерывную sequence начиная с 1;
- `DATA_ROW` содержит точный набор индексов/кривых, а missing sample становится `NaN`;
- DATETIME index принимает Unix nanoseconds, числовой индекс отклоняет non-finite values;
- bounded buffer возвращает backpressure без потери record и продвижения sequence;
- drain применяет records строго по порядку и поддерживает целочисленный limit;
- ошибка row/event atomically восстанавливает dataset, events и append-only journal;
- event upsert/delete сохраняет revision guard и пересчитывает deterministic QC;
- checkpoint создаётся только при пустом buffer и подписывает row count, dataset/events/audit;
- изменение rows, curve version/state, events, QC или checkpoint fingerprint обнаруживается;
- replay с sequence 1 создаёт идентичные rows, events, QC и report projection;
- resume разрешён только после совпавшего checkpoint и проверяет последующие checkpoints;
- closed session требует final checkpoint, canonical UTC close time и final audit digest;
- codec отклоняет unknown fields/kinds, schema mismatch, duplicate IDs и sequence gaps;
- миграция v17 → v18 добавляет пустой `acquisition_sessions` без изменения проекта.


## Versioned lag/depth correction

Для lag correction schema v1, введённой в v19 и сохраняемой в текущем project format v20, обязательны проверки:

- constant-time, annular-volume/flow, pump-strokes и control-points formulas;
- явные TIME/DEPTH indexes и repeated-time aggregation policy;
- отсутствие скрытой экстраполяции: недоступная corrected depth остаётся `NaN`;
- отдельный derived dataset и два DEPTH indexes для каждой immutable revision;
- неизменность acquisition dataset, append-only records и checkpoints;
- source-prefix fingerprint допускает только append, но обнаруживает изменение истории/metadata;
- output fingerprint обнаруживает изменение осей, кривых, параметров и provenance;
- optimistic guard для add revision и activate revision;
- replay/codec отклоняет неизвестные поля, разрывы revisions и tampered output;
- миграция `v18 → v19` добавляет пустой `lag_correction_profiles`;
- UI работает через project-controller, показывает preview и явно выбирает source/corrected axis;
- ReportDefinition фиксирует выбранный dataset/index без скрытого переключения оси.

## Рабочие формы, графические колонки и ежедневное наращивание LAS

Для project format v20, form schema v6 и tablet layout v15 обязательны проверки:

- grid overlay остаётся видимым при скрытых осях и не зависит от состояния pyqtgraph axis;
- каждая колонка отдельно сохраняет grid X/Y, major/minor divisions, alpha и print-grid;
- curve header сохраняет min/max, linear/log, unit, цвет кривой, текста и нижней линии;
- двойной щелчок по шапке маршрутизируется в настройку соответствующей кривой;
- form round-trip сохраняет порядок/ширины, viewport, source dataset/index, revision и scope;
- 19 заводских symbols имеют alpha-канал и tight crop; legacy olive/white canvas удалён;
- новый DEPTH LAS использует редактируемый default step 0,2 м;
- daily append требует явно выбранный dataset и точное совпадение DEPTH/TIME, type, UOM,
  WELL, curve mnemonics и units;
- одинаковое перекрытие пропускается, конфликтующее блокируется до изменения target;
- повторный SHA-256 является no-op, а append history сохраняется при project round-trip;
- append одного dataset не изменяет другие DEPTH/TIME datasets, формы и canvas objects;
- миграция `v19 → v20` добавляет независимый пустой `append_history` каждому dataset.

## Report Passport

Для воспроизводимости отчётов обязательны отдельные headless- и интеграционные проверки:

- одинаковые данные, интервал, форма, язык и render settings дают одинаковый `passport_sha256`;
- изменение значения внутри фактического интервала меняет digest, а изменение за его пределами — нет;
- fingerprint индексной шкалы учитывает только реально использованные значения;
- semantic binding сохраняется полностью: исходная и canonical mnemonic, kind, quantity class,
  source/canonical/display UOM, sensor/source, confidence, aliases, matched_by и evidence;
- source fingerprint использует приоритет import snapshot → embedded LAS → внешний файл с
  предупреждением → normalized report-data snapshot;
- абсолютный output path, время формирования и другие нестабильные поля отсутствуют в подписанном JSON;
- формулы фиксируют ID, версию, provenance и SHA-256 выражения, когда выражение доступно;
- формы и layouts используют content-addressed revision, Masterlog — versioned revision;
- загрузчик sidecar обнаруживает любое изменение подписанного содержимого;
- Print Center, прямой PNG/SVG/PDF, Masterlog PDF и interpretation PDF создают sidecar;
- отмена перезаписи или ошибка построения паспорта не оставляет частично подтверждённый результат;
- физическая печать возвращает digest паспорта, но не создаёт sidecar без output path.

## ReportDefinition и единый интервал

Для schema v2 обязательны отдельные headless- и source-integrity проверки:

- canonical payload и `content_sha256` воспроизводятся и сохраняются при round-trip;
- profile, dataset ID, точный index ID, sections, curve IDs, form revision и language валидируются;
- full/current/custom/selection разрешаются включительно и ограничиваются domain индекса;
- datetime и numeric index используют один resolver без скрытого переключения оси;
- selection без frozen context отклоняется; отсутствующий dataset/index/curve ID блокирует job; ожидаемая отсутствующая мнемоника сохраняется как unavailable;
- Print Center preview и итоговый job вызывают один `_resolve_print_report`;
- после resolve downstream pagination получает exact custom range;
- планшет фиксирует `vertical_index_id`, а DEPTH-selection не предлагается для TIME-view;
- Masterlog preview, PDF и system preview используют одну definition;
- CSV и XLSX используют один `ResolvedReportDefinition`, а не повторно читают UI-selection;
- Report Passport сохраняет canonical definition payload и digest;
- interval-row helper и базовая localization model импортируются без top-level Qt dependency.

## Coverage model

Для Coverage schema v1, ReportDefinition schema v2 и Report Passport schema v4 обязательны проверки:

- конечный `0.0` классифицируется как `observed_zero`, а не missing;
- `NaN` и `Infinity` доступного канала классифицируются как `missing_sample`;
- отсутствующая ожидаемая мнемоника классифицируется как `channel_unavailable`;
- coverage считается только по строкам resolved interval;
- observed + missing = total для доступного канала, unavailable = total для недоступного;
- CSV пишет `0`, пустую ячейку и `#N/A` без взаимной подмены;
- XLSX Parameters, JSON, Parquet, Curve Catalog и interval statistics используют общий анализатор;
- Report Passport schema v4 подписывает coverage, включая unavailable requests;
- ReportDefinition payload v1 мигрируется в runtime schema v2.

## Print media и physical printer gate

Для print-media schema v1 обязательны проверки:

- A4/A3 и portrait/landscape разрешаются в точные физические размеры;
- custom media принимает 25–5000 мм, roll вычисляет длину и ограничивает сегмент 5000 мм;
- Fit создаёт одну horizontal page, 100% использует reference DPI 96;
- overlap меньше printable width и преобразуется детерминированно;
- vertical pages × horizontal continuations имеют стабильный порядок и глобальную нумерацию;
- preview, PDF, paged raster/SVG и printer получают один `PrintJobSettings`;
- прямой PDF создаёт continuations, однофайловый raster/SVG блокирует скрытое clipping;
- системному диалогу передаётся диапазон `1…N`; выбранный range учитывается в gate и результате;
- gate блокирует invalid/error printer, unsupported media, invalid bounds, margins и printable area;
- unsupported requested DPI заменяется ближайшим только с явным warning;
- `tools/physical_print_gate.py` не отправляет реальную печать без `--print-test`;
- Report Passport schema v4 подписывает format/orientation/scale/continuation/margins/DPI.

Аппаратная матрица должна отдельно проверить драйверы офисного A4/A3-принтера и roll plotter.

## Output transaction и artifact fingerprint

Для transaction schema v1 и Report Passport schema v4 обязательны проверки:

- producer пишет только в собственный staging-каталог;
- passport нельзя записать без output artifact fingerprint;
- single-file и paged outputs сохраняют basename, MIME, size и SHA-256;
- изменение готового output обнаруживается при `load_report_passport()`;
- ошибка между установкой output и sidecar восстанавливает прежнюю пару;
- аварийное завершение оставляет journal, который следующий recovery откатывает;
- journal со статусом `committed` сохраняет новую пару и завершает cleanup;
- overwrite удаляет лишние continuation pages транзакционно;
- recovery не разрешает paths за пределами output directory и staging workspace;
- recovery tool безопасен при отсутствии pending journals.

Ручной Windows smoke-test должен принудительно завершить процесс на стадиях rendering, backup и
install для local NTFS и network share, затем подтвердить recovery и совпадение output SHA-256.

## Обязательная матрица ручной проверки

| Область | Сценарий | Критерий |
|---|---|---|
| Открытие | реальные LAS разных поставщиков, CP866/1251/UTF-8 | данные и подписи читаемы, источник не изменён |
| Планшет | depth/time, pan/zoom, F4, выбор трека | нет чёрного кадра, мерцания и потери выделения |
| Сетки | крупные/мелкие X/Y, прозрачность, выключение | экран, preview и PDF соответствуют настройкам |
| Аннотации | создание, drag/resize, Delete/context/manager, смена формы | объект остаётся только в своей области и удаляется всеми командами |
| Редактирование | карандаш, таблица, Undo/Redo, Save/reopen | пересчёт согласован; диск меняется только после Save |
| Masterlog | интервалы, литотипы, legend, callouts, header | preview и PDF не расходятся по данным и геометрии |
| Печать | A4/A3/custom/roll, 100%/fit, landscape/portrait | шкалы читаемы, линии не исчезают, страницы продолжаются корректно |
| HiDPI | 100%, 125%, 150%, 200% | hit-testing и resize handles совпадают с изображением |
| Миграция | проекты до форматов 18/17/16/15/14 | текст, геометрия, bindings и печатные настройки сохранены |

## Golden-render gate

Committed fixtures находятся в `tests/golden_rendering` и обновляются только командой:

```powershell
.\.venv\Scripts\python.exe tools\update_render_goldens.py
```

Обязательные проверки:

- regenerated JSON/SVG совпадают с committed файлами байт-в-байт;
- SHA-256 canonical payload каждого JSON корректен;
- screen px и print mm имеют одинаковые normalized major/minor grid fractions;
- legend сохраняет порядок, deduplication, unknown fallback и RU/KK/EN подписи;
- legacy lithotype alias разрешается в точный factory bitmap с content SHA-256;
- bitmap tile сохраняет physical size при reference DPI 96;
- annotation box, leader endpoint, rotation и clipping согласованы в px/mm;
- fixture не содержит timestamp, абсолютный path, random ID или application version.

Состав и правила описаны в [Golden rendering](GOLDEN_RENDERING.md). Structural/SVG goldens
не заменяют Qt raster/PDF comparison: tolerance документируется отдельно для Windows и
HiDPI 100%, 125%, 150% и 200%.

## Производительность

Минимальная матрица: 100 тыс., 1 млн и 5 млн строк. Измеряются время открытия, первый кадр,
pan/zoom, пиковая память, export и отмена длинной операции. Бюджеты фиксируются до начала
оптимизации; утверждение «поддерживается» не допускается без результата измерения.

## Правило выпуска

Stable разрешён только при зелёном автоматическом gate, подписанной ручной матрице на
целевой Windows-конфигурации и отсутствии незакрытых P0-дефектов. Исключение оформляется
явно с владельцем, риском, сроком и пользовательским обходным путём.

## DOCX и HTML export adapters

Обязательные проверки текущей границы:

- DOCX является валидным Open Packaging Convention ZIP и открывается Word/LibreOffice без repair;
- одинаковый ReportDocumentModel создаёт одинаковые DOCX bytes и HTML text;
- HTML содержит UTF-8, inline CSS и не содержит scripts, external styles или network URLs;
- DOCX не содержит macros, external relationships и embedded objects;
- оба формата используют `report.interval.indices`, а не повторное вычисление диапазона;
- coverage различает `0`, `—` и `#N/A`;
- transaction rollback восстанавливает предыдущий DOCX/HTML и sidecar;
- Passport v4 MIME/size/SHA-256 совпадают с фактическим output;
- RU/KK/EN кириллица, длинные таблицы и browser/Word printing проходят Windows smoke-test.
