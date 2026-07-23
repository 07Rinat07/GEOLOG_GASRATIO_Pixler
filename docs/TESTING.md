# Проверка качества

Актуально на 23 июля 2026 года. Этот файл задаёт один действующий release gate. История
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

Для среза 0.7.37 в текущем контейнере выполнены `compileall`, локальная сборка wheel через `pip wheel --no-build-isolation` и доступный
headless/regression/source-integrity набор: 876 тестов пройдено, 4 платформенных сценария
пропущено, 3 LAS-сценария исключены без `lasio`. Полная коллекция обнаруживает 82
Qt/pyqtgraph/LAS-зависимых test-файла, которые не собираются без `PySide6`, `pyqtgraph` и
`lasio`; один дополнительно собираемый UX-файл требует Qt fixture во время запуска. Ruff и
mypy в контейнере отсутствуют. Стандартная build isolation не смогла скачать `setuptools>=69` из недоступного package index; локальная сборка без скачивания завершилась успешно. Это не заменяет полный gate. Перед стабильным выпуском команды
выше и Windows/HiDPI/PDF/physical-print smoke-test необходимо повторить в установленном
окружении.

## Semantic Channel Dictionary

Для семантической границы обязательны отдельные headless-проверки:

- точное, alias и legacy `S/GID` сопоставление через Sensors-каталог;
- сохранение исходной мнемоники, source UOM, confidence и evidence;
- явный unresolved для неизвестного vendor-канала или UOM;
- UOM quantity conflict как ошибка Import Review;
- round-trip project format v16 и миграция v15 → v16;
- сохранение binding при copy/merge/resample/TIME↔DEPTH;
- read-only гарантия `build_import_review()`;
- plan/preview/commit на глубокой копии без изменения loader-owned dataset;
- ручные index, NULL, channel, canonical, quantity и UOM overrides;
- блокировка commit при ошибках индекса или отсутствии импортируемых каналов;
- отмена CSV/Excel/LAS/Paradox до project-session port;
- одинаковый набор Import Review localization keys в RU/KK/EN.

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

Для coverage schema v1 и report schemas v2 обязательны проверки:

- конечный `0.0` классифицируется как `observed_zero`, а не missing;
- `NaN` и `Infinity` доступного канала классифицируются как `missing_sample`;
- отсутствующая ожидаемая мнемоника классифицируется как `channel_unavailable`;
- coverage считается только по строкам resolved interval;
- observed + missing = total для доступного канала, unavailable = total для недоступного;
- CSV пишет `0`, пустую ячейку и `#N/A` без взаимной подмены;
- XLSX Parameters, JSON, Parquet, Curve Catalog и interval statistics используют общий анализатор;
- Report Passport schema v2 подписывает coverage, включая unavailable requests;
- ReportDefinition payload v1 мигрируется в runtime schema v2.

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
| Миграция | проекты до форматов 16/15/14 | текст, геометрия, bindings и печатные настройки сохранены |

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
