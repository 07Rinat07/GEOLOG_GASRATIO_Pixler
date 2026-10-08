<!-- runtime-contract: package=0.7.96; project=v37; form=v18; layout=v25 -->
# Архитектура

Архитектурные решения обновлены 9 сентября 2026 года. Целевые контракты отмечены отдельно
от действующих механизмов; runtime marker отражает текущие версии схем.

## Архитектурный стиль

DIGITAL GEOLOG GASRATIO&PIXLER — desktop-модульный монолит на Python 3.11, PySide6, PyQtGraph и NumPy.
Модульность определяется направлением зависимостей и контрактами, а не количеством процессов.

```text
UI / tablet widgets / dialogs
              ↓
application controllers / session / jobs
              ↓
domain + calculations + immutable contracts
              ↑
storage / importers / external adapters / plugins

printing / reports consume resolved read models and never own source data
```

Базовые правила:

- `domain` и `calculations` не импортируют Qt, UI, printer или файловые диалоги;
- UI собирает ввод и отображает read model, но не реализует формулы, migration или запись проекта;
- изменяющая операция проходит через controller/session command и управляет `dirty`, rollback и audit;
- importer преобразует недоверенный внешний формат в доменную модель и не изменяет источник;
- renderer получает уже подготовленные массивы и layout, но не исправляет исходные данные;
- сериализуемый контракт меняется только с версией, migration и compatibility tests.

## Пакеты и ответственность

```text
src/geoworkbench/
├── app/               запуск и production composition root
├── calculations/      Qt-независимые формулы и conditioning
├── catalogs/          семантика параметров и справочники
├── data/              LAS-oriented структуры и lossless source
├── domain/            модели и инварианты без UI
├── form_constructor/  модель и ресурсы конструктора
├── forms/             формы, шаблоны и factory catalog
├── importers/         bounded adapters внешних форматов
├── plugins/           версионированные extension contracts
├── printing/          pagination, PDF/printer и page rendering
├── project/           session, commands и project controllers
├── services/          прикладные jobs и orchestration
├── storage/           codec, migrations, atomic persistence
├── tablet/            layout, sampling, interaction и Qt view
├── ui/                окна и диалоги PySide6
└── visualization/     renderer-neutral модели визуализации
```

Production-сборка приложения использует один `ApplicationContext`, создаваемый в `app`.
Он владеет factory project storage scope, semantic mnemonic registry, import/report services,
WITSML/ETP credentials и audit sinks. Каждый MainWindow получает отдельный `ProjectScope`,
поэтому mutable `ProjectSession` и repository не разделяются между окнами, а process-wide
registry/report/security services переиспользуются явно. UI-диалоги WITSML/ETP получают
credential/audit ports из composition root вместо скрытого создания вторых infrastructure
экземпляров. Изолированный fallback без context сохранён только для unit/UI tests и embedding.
`MainWindow` остаётся shell/composition UI; дальнейшее дробление feature orchestration относится
к ARCH-02. Первый ARCH-02 slice выносит WITSML project registration в
`WitsmlImportCoordinator`: оба UI-входа (WITSML 2.x file review и WITSML 1.4.1.1 Store)
передают уже проверенный `WitsmlImportCommit`, а coordinator определяет target well policy и
делегирует атомарную регистрацию application controller. Следующий ARCH-02 slice оставляет
lag-correction source/projection selection внутри `LagCorrectionProjectController`: MainWindow
только открывает диалог и отображает ошибки, не меняя `ProjectSession.current_dataset_id`.
Третий slice переносит conditioned Gas Ratio/Haworth/Pixler persistence в
`GasRatioProjectController`; Qt получает immutable calculation outcome и больше не вызывает
mutating gas-ratio API сессии напрямую. Четвёртый slice консолидирует GS2 import: один
`MainWindow.open_gs2()` собирает только UI-выбор, а `Gs2ImportCoordinator` владеет Dataset
enrichment и регистрацией; production subclass больше не содержит второй GS2 workflow.
Пятый slice собирает перенос пользовательских canvas-объектов через
`CanvasObjectTransferCoordinator`: controller, transactional workflow и material autosave
остаются за application boundary и вместе rebind-ятся на новую ProjectSession. Шестой slice
переводит WELL-02 late-analysis import на `LateAnalysisCoordinator`: source adapter, reviewed
transaction и baseline/completion state больше не собираются вручную в Qt-shell. ARCH-02
закрывается общим AST/source-contract: оба MainWindow-слоя не могут напрямую присваивать
ProjectSession/project/Dataset/Well state или возвращать ad-hoc mutation workflows.
ARCH-03 начинается с Curve Pencil: renderer/UI остаются в `TabletView`, а editing session state
(target, mode, gesture points, commit/history/unsaved flags) принадлежит Qt-независимому
`CurvePencilState`. Второй slice ARCH-03 переносит проекцию visible range на scrollbar
и обратное преобразование в `TabletNavigationCoordinator`; Qt-view только применяет готовый
`NavigationControlState` к widgets и передаёт пользовательское значение обратно coordinator.
Третий slice ARCH-03 переносит interpretation interval editing-session state в
`IntervalEditingState`: active mode, default interval type и in-progress gesture больше не
принадлежат QWidget; Qt-view сохраняет preview graphics, cursors и signal emission.
Четвёртый slice ARCH-03 устраняет параллельное хранение interval selection в `TabletView`:
`SelectionManager` становится единственным владельцем выбранного interval, а
`InterpretationSelectionState` хранит active interpretation и синхронизирует контекст.
Пятый slice ARCH-03 объединяет geometry/static caches, dirty registry и overlay layer manager
под `TabletRenderState`; view использует совместимые delegates, а invalidation policy живёт в
Qt-независимом owner-компоненте. Финальный ARCH-03 contract запрещает возвращать legacy
mutable state в `TabletView.__init__`, подтверждает композицию headless state-компонентов и
отсутствие top-level Qt dependency у state modules; sampling остаётся stateless/headless, а
track topology lifecycle — за `TrackLifecycleCoordinator`.
ARCH-04 начинается с immutable `SemanticContext`: importer передаёт exact source mnemonic,
mapped mnemonic, source UOM, canonical hint и mapping evidence вместе с deterministic Sensors
catalog version. `SemanticChannelDictionary.resolve_context()` проверяет version pin; legacy
`resolve()` остаётся compatibility shim. Первый production consumer нового boundary — LAS;
второй slice переводит CSV/TXT import и фиксирует column/header mapping evidence. Третий slice
переводит GeoScape/Paradox и фиксирует field ordinal/name/type и mapped mnemonic evidence.
Четвёртый slice переводит WITS0 Import Review и фиксирует record/item/source-id, automatic/reviewed
mapping state и catalog version evidence. Пятый slice переводит общий WITSML Import Review
(2.x ChannelSet и нормализованный WITSML 1.4.1.1 flow) и фиксирует channel position/key/uuid,
automatic/reviewed/commit mapping state и catalog version evidence. Шестой slice переводит
общий post-import `ImportReviewController`: legacy inspection и reviewed remapping используют
тот же context boundary, а manual override сохраняет исходное importer evidence. Седьмой slice
переводит ETP 1.2 Import Review: channel URI/id и automatic/reviewed/commit mapping state
становятся version-pinned semantic evidence. Финальный production-wide AST/source-contract
запрещает legacy `SemanticChannelDictionary.resolve()` у production consumers; метод остаётся
только compatibility shim внутри semantic dictionary.
ARCH-05 закрепляет нижние вычислительные слои как Qt-независимые: recursive AST/import-contract
проходит каждый Python-модуль `domain` и `calculations`, нормализует absolute и relative
imports и запрещает зависимости на PySide/PyQt, PyQtGraph/qtpy, `geoworkbench.ui` и
`geoworkbench.printing`. Запрет действует независимо от того, находится import на верхнем
уровне, внутри функции или под `TYPE_CHECKING`; UI/printing остаются внешними adapter/composition
слоями и могут зависеть от domain/calculations, но не наоборот.
ARCH-06 делает выбор расчётного поведения явным versioned contract. Existing sourced
`FormulaProfile` остаётся immutable и versioned; conditioned Gas Ratio получает отдельный
`GasRatioCalculationProfile`, а `CurveContinuityPolicy` — immutable `policy_id/version`.
UI выбирает profile DTO из каталога и передаёт его в `GasRatioProjectController`; controller
фиксирует profile/policy identity в dataset parameters и передаёт DTO в calculations.
Формулы Gas Ratio/Haworth/Pixler и bounded interpolation не дублируются в UI.

## Источник, рабочая модель и экспорт

```text
external source (LAS/GS2/WITS/WITSML)
              ↓ bounded import + semantic resolution
immutable source evidence + normalized Dataset
              ↓ application commands
project state + derived curves + annotations/layout
              ↓ resolved report definition
PDF / printer / LAS / CSV / XLSX / DOCX / HTML
```



### Report presentation composition

`InterpretationReportComposition` — renderer-neutral project state, keyed by `dataset_id`.
Он хранит только presentation choices (page orientation, print order, cuttings/LBA visibility)
и сериализуется в project format v37. `ProjectSession` является runtime owner, storage codec —
единственная persistence boundary, а Qt dialog только редактирует модель. Preview, PDF и
system print читают одну composition; renderer-specific Qt enums не попадают в persisted schema.
Старые проекты мигрируют с пустой composition и безопасными factory defaults.
Persisted report annotations принимают только целочисленную поддерживаемую `schema_version`:
JSON boolean, float, string и неизвестные версии отклоняются на storage boundary через
`ProjectFormatError`, до материализации загружаемого документа.

`ReportChartPanelSettings` хранит полный порядок разрешённых logical panel keys и отдельную
скрытую выборку: скрытие не теряет позицию. Domain validator ограничивает оба массива четырьмя
ключами и отвергает неизвестные/повторённые элементы. Один `report_curve_panels` сопоставляет
исходные evidence channels, затем применяет presentation selection; поэтому hiding не меняет
method matching/calculation. Renderer geometry и annotation track maps получают уже разрешённые
панели, без fallback отсутствующих anchors на соседнюю колонку. Old v37 без `chart_panels`
получает исторический profile-specific порядок; custom order/hidden входят в render options
Report Passport отдельно от исходного dataset digest.
Presentation resolution имеет O(4) память/упорядочение и не копирует Dataset или arrays.
Скрытые панели пропускаются до inspection исходных кривых; method matching продолжает
использовать полный профиль, поэтому скрытие не меняет сопоставление evidence channels.

### Report presentation labels и source identity

Report DTO и Dataset сохраняют exact source mnemonic для воспроизводимости расчёта и аудита.
Пользовательский presentation layer не должен выводить vendor/source codes напрямую, если
`parameter_labels` или semantic/Sensors resolver однозначно знает физический параметр.
Графики, HTML/PDF, DOCX и видимые XLSX-листы используют общий localized display contract;
скрытые source/audit sheets и доменные поля сохраняют исходную мнемонику без потери provenance.
Та же граница применяется к RU/KK/EN fluid terminology: вычислительный code остаётся стабильным,
а локализованный отчёт отображает фазовую формулировку без превращения предварительного evidence
в доказанный тип залежи.

Исходный LAS/GS2/raw artifact, source mnemonic, unit, mapping evidence и fingerprint являются
доказательствами происхождения. Производная кривая не подменяет source-кривую и получает
versioned provenance. Экспорт является проекцией проекта и не заменяет `Ctrl+S`.

Постоянная session panel делает границу видимой оператору как цепочку
`Источник → Файл проекта → Экспорт`: источник остаётся read-only, файл проекта показывает полный
путь либо состояние «не сохранён», а LAS всегда является отдельным результатом. Прямой
Paradox- и GS2-импорт передаёт действие **«Сохранить LAS»** в единый `DatasetExportController`
только после успешной регистрации Dataset. Отмена Import Review, закрытие диалога и ошибка не
создают export job. `SessionSafetyController` защищает dirty-сессию при закрытии четырьмя
исходами: сохранить проект, экспортировать LAS-копию, закрыть без сохранения или отменить.
`ProjectFileSafetyService` реализует PROJ-02 вне Qt: стабильное чтение и SHA-256 fingerprint,
optimistic external-change check, staging рядом с target, проверку повторным открытием,
self-contained backup прежней ревизии и атомарный commit. После commit ротация не может
превратить успешное сохранение в ложный rollback: её ошибки возвращаются как warnings.

`ProjectController` хранит `ProjectDiskState` открытой ревизии. Обычный `Ctrl+S` и material
autosave сравнивают canonical bundle с этой базой; изменение синхронизацией блокирует overwrite.
Daily LAS требует `.geologpkg` до mutation и после реального append вызывает
`SaveMode.MATERIAL_AUTOSAVE`. Duplicate/no-op не пишет файл и не создаёт backup. Пять последних
проверенных копий каждого project path индексируются в `.geolog-backups`; recovery всегда
восстанавливает выбранную копию как новый `.geologpkg`, не заменяя active/canonical файл.

### Переносимый проект и ежедневный LAS

`ProjectRepositoryRouter` сохраняет legacy `.geolog.json` через прежний repository, а
`.geologpkg` — через атомарный ZIP-контейнер. Пакет содержит `project.geolog.json`, raw LAS и
image assets, а `manifest.json` фиксирует путь, размер и SHA-256 каждого элемента. Reader до
распаковки проверяет число файлов, суммарный размер, коэффициент сжатия, повторяющиеся и
небезопасные пути; затем проверяет хэш каждого payload и только после этого вызывает project
codec v30.

Preview ежедневного append дополнительно хранит два transient fingerprint
`dataset_append_state_sha256` (контракт `daily-las-preview:1`). Они связывают подтверждение с
числовыми массивами, активной осью, единицами, LAS headers, происхождением/состоянием кривых и
историей источников обоих Dataset. Повторный анализ непосредственно перед mutation должен дать
тот же план, включая оба fingerprint; одинаковых счётчиков строк недостаточно. UI сбрасывает
план и controller state перед каждой попыткой анализа, при смене входа и отмене окна.
Печатные названия и ручные well-level слои не входят в numerical append и не инвалидируют его.
Fingerprint не сериализуется; исторические audit hashes сохраняют свой формат; массивы
хэшируются в прежнем C-order блоками до 131 072 элементов без полной временной bytes-копии.

Для legacy explicit save safety-слой пишет полный bundle в owned staging, устанавливает только
отсутствующие content-addressed assets без удаления orphan-файлов и заменяет JSON-манифест
последним. Material autosave legacy запрещён: UI сначала переводит рабочую сессию в `.geologpkg`.

`LocalLasFolderProvider` является read-only adapter локальной папки, которую синхронизирует
внешний серверный клиент. Он не управляет сетью и не удаляет файлы. Daily append сначала строит
немутирующий план, затем готовит все NumPy-массивы и фиксирует source revision, provider,
before/after Dataset SHA-256 и raw artifact. Перед commit контроллер снова хэширует выбранный
файл; `WELL`, `UWI` и `API` отклоняют явное смешение скважин. Схема сравнивается по исходным
LAS-кривым. Добавленные в проекте, перенесённые и расчётные кривые сохраняют старый участок и
получают `NaN` на новых строках; расчётные результаты становятся `STALE` до повторного расчёта.
Well-level ручные слои и языковые тексты не входят в числовую замену и сохраняют стабильные
идентификаторы. После append начальный LAS остаётся шаблоном заголовка для обычного экспорта, а
паспорт отчёта включает fingerprints всех сохранённых source revisions.

Авторские тексты используют карты `ru`/`kk`/`en` и отдельные language revisions. Общие числа,
геометрия интервалов и кривые не дублируются. UI и печатный renderer разрешают текст выбранного
языка; legacy scalar-поля остаются fallback для проектов v1–v22.

## Газовый conditioning и расчётная граница

Профессиональный газовый workflow закреплён как последовательность:

```text
resolved source C1–C5
        ↓ immutable conditioning copy
common monotonic depth basis + bounded short-gap interpolation
        ↓
TG_CALC / relative components / Haworth / isomer ratios / Pixler
        ↓
shared viewport geometry
        ↓
screen / preview / PDF / printer
```

### Реализованные компоненты

- `calculations/gas_conditioning.py` содержит `GasConditioningPolicy`,
  `ConditionedGasComponents`, `interpolate_bounded_gaps()` и `condition_gas_components()`.
- `calculations/gas_ratio.py` содержит низкоуровневый совместимый `calculate_basic_ratios()` и
  production entry point `calculate_conditioned_ratios()`.
- `ProjectSession.calculate_basic_gas_ratios()` разрешает source-компоненты через semantic
  resolver, кондиционирует их по `dataset.depth` и только затем создаёт производные кривые.
- `tablet/geometry_cache.py` ограничивает render-only short-gap policy газовыми мнемониками и
  сохраняет контекстные точки на границе viewport.

### Изолированный контур ОПУС

ОПУС не входит в стандартный `calculate_conditioned_ratios()` и запускается отдельной
командой `InterpretationCalculationController.calculate_opus_curves()`. Semantic resolver
приводит поддерживаемые исходные `ppm`/`ppb`/fraction/percent к `% об.`, но не изменяет
source arrays. Контур создаёт только versioned curves с provenance
`calculation:opus-screening:1.0`: рабочие абсолютные C1–C5/Total в `% об.`, относительные
`OPUS_P1-P5` и четыре проверяемых исторических индекса. Справочный `OPUS5_REF`
из vendor-профиля не выполняется: ему нужен независимый TotalGas, а открытого
первичного источника формулы и порогов не найдено.
`services/opus_interpretation.py` строит отдельную report model. Ограничения
фона/контраста квалифицируют применимость классификации ОПУС, но не удаляют найденные
газовые аномалии. Для интервала строится пересечение опубликованных перекрывающихся
диапазонов четырёх показателей только по отсчётам, превысившим порог аномалии;
подпись флюида выдаётся только при единственном совместимом классе. При
неоднозначности автоматическая подпись использует явно помеченную резервную гипотезу
Haworth/Pixler; основа решения сохраняется в evidence.
Общий exporter сохраняет полный ряд
Dataset. Стандартная report model не содержит ОПУС-метод.

Расширение **`OPUS Gasomer`** реализовано как второй versioned profile внутри того же
изолированного контура, но не меняет профиль `opus-lukyanov-c1-c5-relative-1987-1997`.
Его знаменатель — отдельный синхронный TotalGas; пять индикаторов получают имена
`OPUS_GM_1…OPUS_GM_5`, чтобы не столкнуться с существующими `OPUS3/OPUS4`. Versioned JSON и
чистое vectorized-ядро в `calculations.opus_gasomer` выполняют синхронный построчный расчёт,
точное ppm↔`% об.`, LOD/QC states и уникальную моду с явной ничьей без изменения source arrays.
Тот же слой агрегирует поддержку синхронных классов внутри интервала и хранит class/QC/vote
distributions. Legacy MAX возвращается только отдельным compatibility-result с explicit
maximum span и source depth каждого максимума. Чистый detector использует локальный robust
фон, `ΔTG`, robust z-score и контраст
с обязательным приборным LOD-floor; `0,1 % об.` является warning источника, а не блокирующим
условием. Параметры detector хранятся в том же versioned JSON и помечены как engineering
defaults до полевой калибровки. Для строго регулярной depth-оси rolling median/MAD выполняется
векторно bounded-блоками до `1 500 000` window elements; нерегулярная монотонная ось сохраняет
физический two-pointer fallback. Поэтому memory зависит линейно от выходных массивов, а
временное rolling-окно имеет фиксированный верхний budget.

`HydrocarbonInterpretationReport.opus_gasomer` хранит immutable snapshot прямого результата:
версию/статус профиля, точные формулы, source curve identities и units, LOD, detector evidence,
класс/support интервала, пять медианных значений/голосов, QC distributions и workbook
provenance. HTML, PDF/печать, XLSX и DOCX читают этот snapshot и не пересчитывают значения.
UI принимает LOD независимого TotalGas в исходной единице; ноль означает отсутствие LOD и
запрещает запуск локального detector без удаления исторического отчёта.
Legacy-расчёт по независимым MAX допускается только для одного выбранного короткого интервала и
получает отдельный compatibility marker. Полный контракт:
[OPUS_GASOMER_IMPLEMENTATION.md](OPUS_GASOMER_IMPLEMENTATION.md).

`InterpretationMethodStatus` хранит не только источник и доступные кривые, но и
поле `calculation`. HTML/PDF, DOCX и лист XLSX **«Методика»** выводят его как
паспорт формул и правила интерпретации. Для ОПУС источник явно разделяет независимую
открытую сверку `OPUS3/OPUS4`, вторичную сверку `OPUS_K1_3/OPUS_1_5` и условия
применимости из статьи 2022 года; профиль не называется ГОСТ/ISO-стандартом.

### Инварианты conditioning

1. Source depth и source component arrays не мутируются.
2. Ось может возрастать или убывать; монотонные duplicate-depth rows поддерживаются.
3. Интерполируются только отсутствующие строки между двумя конечными измерениями.
4. Ведущие/хвостовые пропуски и длинная остановка регистрации остаются `NaN`.
5. Реальный конечный ноль не перезаписывается; на логарифмической шкале он остаётся разрывом.
6. Допустимый gap рассчитывается по плотной части фактического cadence и может иметь абсолютный cap.
7. Для каждой source-кривой возвращается boolean mask интерполированных строк и использованный gap.
8. C4/C5 не учитываются дважды: полная пара изомеров имеет приоритет над aggregate channel.
9. Derived arrays имеют ту же длину и порядок строк, что и Dataset.
10. Recalculation обновляет существующую derived curve, а не создаёт дубликат.

### Единая граница непрерывности

`calculations/curve_continuity.py` является единственным источником правил cadence, bounded gap interpolation и segment connectivity. Calculation conditioning применяет его к immutable рабочим копиям C1–C5 до формул, а viewport sampling — к полному массиву до обрезки и downsampling. Renderer получает явный boolean connect mask; длинные остановки, края без данных и логарифмические нули остаются разрывами. Dataset и исходный LAS не изменяются.

## Семантическое разрешение

Глобальный mutable catalog не является источником истины. Каждый import/replay/calculation должен
получать immutable `SemanticContext` либо эквивалентный versioned resolver result и сохранять:

- source mnemonic и description;
- canonical parameter/property kind;
- source и canonical UOM;
- confidence/evidence;
- версию каталога и формулы.

Неоднозначное сопоставление не разрешается молча. UI показывает выбор, а application command
получает уже подтверждённый mapping.

## WITS0 операторский workspace и real-time аналитика

WITS0 разделён на четыре слоя ответственности:

1. **Acquisition/raw boundary** принимает TCP-поток, сохраняет неизменяемый raw и создаёт reviewed
   append-only Dataset только через application/controller boundary.
2. **Headless live projection** строит bounded read-only snapshot, ось, current values, quality
   markers и downsampling. Он не знает о QWidget и не реализует формулы Gas Ratio/Pixler/DEXP.
3. **Headless analytics** использует существующие versioned calculation profiles и UOM dictionary.
   Live-derived WH/BH/CH, Pixler и DEXP/DEXPC должны вычисляться теми же функциями, что batch/offline.
   Gas-origin classifier является отдельным stateful service и не подменяет fluid interpretation.
   Alarm evaluator также отдельный headless component; threshold alarm не является geological show.
4. **Qt operator adapter** отвечает только за формы, layout, fullscreen, badges, help/tooltips,
   audio/visual presentation и команды Save/Reset/Acknowledge/Mute.

Factory live forms являются defaults, а пользовательские overrides сохраняются по canonical mnemonic,
не по session-specific curve_id. Это позволяет пережить reconnect и новый Dataset без неявного
переноса stale IDs.

Interpretation marker содержит фактический axis anchor и presentation metadata. UI может сместить
горизонтальный badge для устранения наложения, но не имеет права менять координату самой линии/
полосы события. Fluid-screening marker, gas-origin marker и threshold-alarm marker независимы.

## ProjectSession и команды

`ProjectSession` является application boundary текущего проекта. Он выбирает current well/dataset,
владеет dirty-state и вызывает доменные/расчётные операции. UI не должен напрямую изменять
`project.wells`, `Dataset.curves`, layout collections или source sidecars.

Для сложных изменений используются:

- validation до первой записи;
- checkpoint/transaction;
- полный rollback при ошибке;
- один commit и один dirty transition;
- audit/provenance без секретов и абсолютных пользовательских путей.

### Application command history

Обратимые изменения проекта постепенно консолидируются в
`geoworkbench.services.edit_history.CommandHistory`. История ограничена по размеру и хранит
гетерогенные `UndoableCommand` в одном хронологическом порядке; стек меняется только после
успешного execute/undo/redo, а новый command полностью инвалидирует redo-ветку. Команда несёт
`history_domain` и описание, но UI не получает права напрямую менять модель.

Первый ARCH-07 инкремент подключает к одному экземпляру history `CurveEditingController` и
`HeaderEditingController`. Второй подключает `CurveMetadataController` через
`CallbackCommand`: доменный controller сохраняет ownership validation/conflict/restore правил,
а application history отвечает только за chronological ordering и branch semantics. Это позволяет
metadata update/create/remove участвовать в общем Undo без копирования их инвариантов в UI или
generic history service. Для creation-undo guard сравнивает фактический baseline
(metadata + пустые NaN values), а не монотонную curve version: поэтому полностью отменённая
последующая правка не блокирует следующий Undo создания, тогда как отличающееся текущее состояние
по-прежнему fail-closed.

Третий инкремент переводит `CurveTransferController` на тот же history boundary. Одна операция
переноса нескольких кривых хранится одной typed command, а controller сохраняет dataset identity,
metadata и value conflict guards. Guard сверяет фактический baseline перенесённой кривой вместо
монотонной версии объекта: если последующая Curve Pencil правка полностью отменена, Undo переноса
снова допустим; если metadata или значения реально отличаются, операция остаётся fail-closed.

Четвёртый инкремент переводит `DatasetMergeController`. Каждое сращивание хранит собственный
reversible state: исходный dataset, производный dataset, layout и lossless/import sidecars.
Благодаря этому один controller поддерживает несколько последовательных Merge Undo/Redo в общем
chronological stack. Conflict guard использует factual content signature с именем, типом,
depth-domain, depth, headers/parameters, curve metadata и values, но намеренно не включает
монотонный `curve.version`: полностью отменённая последующая правка не блокирует Undo, тогда как
реально изменённое содержимое, удалённый/подменённый результат или исчезнувший target fail-closed.
Для UI-сценария «создать merge → экспортировать файл» `CommandHistory.checkpoint()` фиксирует
undo/redo stacks до первой mutation. Если файловый экспорт завершается ошибкой, project rollback
сначала восстанавливает модель, затем history checkpoint возвращает прежние stacks, включая
существовавшую redo-ветку; неуспешная транзакция не оставляет фантомную merge-команду.

Пятый инкремент переводит in-place `ExternalLasInsertController`. Одна вставка одного или
нескольких каналов внешнего LAS хранится одной typed command; несколько последовательных вставок
образуют обычную chronological цепочку. Command сохраняет dataset identity, manifest state,
исходные metadata и values вставленных кривых. Undo сравнивает фактическое текущее состояние,
поэтому полностью отменённая Curve Pencil/metadata правка не блокирует предыдущую вставку только
из-за увеличившегося `curve.version`; реально отличающиеся metadata/values, удалённая или
подменённая кривая по-прежнему fail-closed. `create_copy()` намеренно остаётся отдельным
derived-dataset workflow и не маскируется как in-place edit.

Шестой инкремент переводит `LithologyController`. Add/Update/Delete записываются в общий
history как bounded callback commands. Команда хранит только один изменяемый
`LithologyInterval` и связанные ключи translation tracking: description status/source,
depth/lithotype dependency revisions, language revisions и content revision. Полная коллекция
литологии и весь Well не копируются. Undo/Redo сначала сравнивает фактический interval и sidecars
с ожидаемым состоянием, проверяет overlap при восстановлении и только затем применяет mutation;
внешнее изменение остаётся fail-closed. Identity объекта интервала сохраняется через весь цикл
Add → Undo → Redo и Update/Remove.


Глобальные действия MainWindow маршрутизируют верхнюю команду к контроллеру соответствующего
домена, чтобы curve undo продолжал выполнять dependency recalculation, header undo — snapshot
conflict check, curve-metadata undo — dataset identity/metadata/value/order checks, curve-transfer
undo — atomic removal/restore перенесённого набора, а dataset-merge undo — atomic removal/restore
производного dataset и его sidecars. Локальные Curve Pencil, Data Inspector, Curve Transfer и
Dataset Merge controls проверяют тип верхней команды и не перескакивают через более новое
изменение другого домена. При смене project/session общий history очищается через существующий
session binding reset boundary. Остальные специализированные undo/redo стеки считаются migration
backlog ARCH-07, а не второй утверждённой архитектурой.

## Утверждённая модель ведения одной скважины на трёх языках

Принята пользователем 5 сентября 2026 года. **Целевой контракт WELL-01…06, ещё не реализованный
полностью.** Статусы ведутся в [PROJECT_PLAN.md](PROJECT_PLAN.md), критерии — WFLOW-001…006 в
[REQUIREMENTS.md](REQUIREMENTS.md). Основа — действующие Well/Dataset, `.geologpkg`, языковые
поля и source registry; новая БД, второй набор кривых на каждый язык или переписывание приложения
для этого сценария не требуются.

Реализованный WELL-01: необязательный `Well.passport` хранит `values`, `texts_i18n` и
`logo_refs`. Числа/даты/координаты проходят проверку типов, конечности, диапазонов и порядка
дат; пять строк конструкции A4 имеют общие диаметры/глубины и названия RU/KK/EN. Контроллер
принимает независимый черновик атомарно, проверяет текущую скважину и доступность assets.
Новое назначение customer/contractor logo дополнительно обязано ссылаться на asset, зарегистрированный
в project `logo_catalog`; произвольный raw image asset отклоняется. Уже сохранённая legacy raw-logo
ссылка может остаться неизменённой при редактировании других полей, чтобы не ломать старые проекты.
Контроллер обновляет `content_revision` и ревизии изменённых языков. Пустой активный паспорт авторитетен;
`None` сохраняет старое разрешение полей через шаблон/LAS. Интервал печати и масштаб остаются
в макете. Отсутствие ключа роли логотипа сохраняет логотип макета, пустая ссылка скрывает его.

Миграция v24 → v25 не выбирает паспорт из конфликтующих шаблонов: она сохраняет их реквизиты,
переводы, геометрию и ID, связывает узнаваемые ячейки `casing_0…4` с полями паспорта, сохраняя
исходный текст для просмотра без паспорта. Выбор legacy-источника выполняется отдельно для
каждого поля в диалоге. Обе ориентации читают паспорт выбранной скважины одним resolver;
зависимость от активного LAS исключена. Необычные пользовательские текстовые элементы
подключаются к паспортным полям через редактор шапки. JSON и `.geologpkg` проверяют ссылки
на логотипы до записи и при чтении; используемый паспортом asset нельзя удалить.

| Владелец | Данные и границы ответственности |
|---|---|
| Well / общий паспорт | Реквизиты скважины, конструкция, роли логотипов и ссылки на assets; переводимые значения отдельно от общих чисел/дат/координат |
| Dataset / source registry | Исходные измерения и поставки, source fingerprints, оси/единицы; язык не влияет на identity или значения |
| Запись геологического слоя | Устойчивый ID, собственный интервал, структурированные значения и RU/KK/EN-тексты; происхождение, ручные overrides и ревизии |
| Многоязычный блок описания | ID/версия шаблона, сохранённые тексты и параметры, порядок блоков, языковые ручные дополнения и состояние перевода |
| Семейство формы | Книжная/альбомная геометрия, bindings по ID, локализованные подписи и явные overrides; экземпляр не владеет копией скважинных данных |
| Задание выпуска | Одна сохранённая ревизия, выбранный интервал, формы, языки, ориентации и состояния отдельных результатов |

Общий паспорт не равен текущему `ReportPassport`: первый содержит редактируемые данные
скважины, второй фиксирует происхождение и параметры конкретной выдачи. Макеты получают
паспорт, интервалы, справочник и язык через read model. Фактическая глубина скважины, диапазон
набора данных и выбранный интервал печати — разные величины; режим ручного значения либо
привязки задаётся явно. Выбор языка не перезаписывает числа и не переводит имена собственные
без введённого пользователем варианта.

Обновление скважины выполняется application-командой: анализ → неизменяемый план изменений
→ подтверждённый diff → повторная проверка source/project revisions → применение → проверенное
сохранение. План разделяет новую глубину, заполнение пропусков и correction. Existing
`DailyLasGrowthController` остаётся основой строгого append; он пока не достраивает кодовую
геологию заполненных слоёв. Новый merge сопоставляет записи по устойчивым ID/источнику, оси и
диапазону, добавляет непокрытые части и сохраняет ручные значения/тексты. Ноль не является
пропуском; пропущенное поле поставки не является командой очистить поле проекта.
Стратиграфия, литология, шлам, анализы и описания сохраняют собственные границы. На общей
границе интервалов правила принадлежности точки должны быть детерминированными без дублей.

Профиль фирмы/источника и его версия участвуют в разрешении rock-code через PROJ-09.
Изменение mapping не переназначает старые интервалы молча; correction показывает затронутые
записи. При отсутствии подтверждённого соответствия сохраняется исходный код с явным
неопознанным статусом. Повтор поставки идемпотентен. Пересчёт и отметка устаревания касаются
зависимых данных, а не всех сохранённых участков. Ошибка подготовки/применения откатывает
изменение; ошибка последующей записи сохраняет прежний диск и recoverable dirty-состояние
с явным сообщением, без сообщения об успешном завершении. Backup/atomic write используют
существующий storage boundary.

Редактор хранит черновики RU/KK/EN отдельно от отображаемого fallback; открытие вкладки
не записывает оригинал как готовый перевод. Перевод зависит от ревизии исходного поля/блока
и использованных параметров. Общие `language_revisions` нужны для invalidation, но не заменяют
состояние отдельных полей. Обновление каталога шаблонов не меняет сохранённый снимок описания;
явное применение новой версии сохраняет ручные дополнения и помечает зависимые переводы.
Подробная политика — [I18N.md](I18N.md).

Ориентация хранится в разрешённой конфигурации печати однажды для листа, шапки и колонок.
Выбор шапки меняет этот параметр; выбор листа разрешает парный макет того же семейства.
Произвольный выбор первого совместимого шаблона из чужого семейства запрещён. Универсальная
шапка и явный режим без шапки сохраняются. Языковые overrides размещения допустимы внутри
семейства при сохранении общих bindings и данных. Renderer проверяет переносы/метрики текста,
а не поворачивает изображение всего планшета.

Пакетный выпуск строится поверх существующих `ReportDefinition`, `PrintJobExecutor` и
output transactions. Сначала фиксируется одна сохранённая ревизия и её готовность на выбранном
интервале, затем все outputs читают этот snapshot. Язык приложения — значение по умолчанию;
выбор нескольких языков выдачи не меняет настройку интерфейса во время рендера. Задание
фиксирует успех/сбой каждого результата; повтор использует исходную ревизию, а не текущую
изменившуюся сессию. PDF уже выполненного выпуска не обновляются вслед за проектом.

Миграция вводится с кодом и повышением схемы в соответствующем инкременте. Она сохраняет
legacy-поля, ID, переводы, изображения и ориентационные overrides. Различающиеся реквизиты
старых шапок не объединяются произвольно: исходные варианты удерживаются до выбора общего
значения. Старые тексты не получают автоматически статус проверенных переводов. Текущее
утверждение архитектуры не меняет формат существующих файлов.

## Импортные jobs

`services/import_jobs.py` маршрутизирует стабильные source types в единый
`DatasetImportJobExecutor`. Qt выбирает файл, собирает подтверждение и показывает результат.
Executor выполняет bounded read/parse, semantic mapping, import report и атомарную регистрацию.
Отмена, отказ validation или exception не оставляют частично добавленный Dataset.

LAS/XML/adapters обязаны ограничивать bytes, elements, nesting, text, attributes, allocations и
время до materialization. DTD/external entity и недоверенные пути запрещены.

## Планшет и rendering

`VerticalRulerLayout` является единственным источником глубинных/временных отметок для всего viewport или печатной страницы. `VerticalRulerScaleSettings` задаёт общую частоту, а `VerticalRulerTrackSettings` может только скрывать ось, подписи или часть общего набора рисок. Колонка не рассчитывает собственный шаг, значения или Y-координаты. Контракт сохраняется в tablet layout v22 и form schema v14; старые layouts и формы мигрируют к automatic/visible defaults.

`TabletLayout` — декларативная сериализуемая модель треков, bindings, шкал, сеток и видимости.
Общая вертикальная ось синхронизирует треки; X независим. Экран виртуализирует viewport, а
geometry cache хранит только производную геометрию, не source arrays.

Числовая шкала X и сетка являются разными presentation-контрактами. `show_x_scale` управляет
видимостью числового диапазона и инженерной линейки в шапке графической колонки, тогда как
`grid_x` управляет только вертикальными линиями сетки внутри графика. Один флаг не выводится из
другого. Изменение из инспектора проходит через controller mutation, а screen, preview, PDF и
printer читают один сохранённый `TrackDefinition`. Контракт сериализуется в form schema v17 и
tablet layout v25; формы v1–v16 и layouts v1–v24 мигрируют с `show_x_scale=True`. Только factory
секция **«Интегрированный газовый каротаж C1–C5 / Компоненты C1–C5»** явно задаёт
`show_x_scale=False`, сохраняя для каждой C1–C5 кривой `LINEAR` и индивидуальный auto-range.

`tablet_view.py` всё ещё содержит значительную orchestration-нагрузку. Новая логика должна
сначала появляться в Qt-независимом controller/service с unit tests, после чего view только
маршрутизирует сигналы и применяет read model.

Screen и print не должны иметь разные формулы. Разрешены разные LOD/typography, но одинаковые:

- source/derived curve identity;
- vertical range;
- finite/gap semantics;
- segment boundaries;
- scale/range settings;
- annotations и interval bindings.

## Печать и отчёты

`PrintJobExecutor` — единственная application-точка printer/PDF/page-export jobs. UI выбирает
назначение и подтверждает действия, но не вызывает renderer напрямую.

`ReportDefinition` фиксирует dataset/index, sections, curve IDs, locale, form revision и interval.
Resolver возвращает один неизменяемый resolved range для preview, PDF, printer и tabular export.
Renderer работает в миллиметрах, строит vertical/horizontal continuations и не является простым
скриншотом viewport.

При повторе шапки колонок в конце журнала pagination добавляет отдельную финальную страницу
для каждого горизонтального продолжения. Страницы графика не резервируют место под нижнюю копию
и не меняют плотность depth/time-to-pixel. Финальная шапка рендерится по ширине той же области,
что и планшет; renderer не имеет права уменьшать её по горизонтали ради размещения рядом с
графиком.

`ReportPassport` сохраняет канонический payload, source fingerprints, semantic bindings, версии
формул, form/template revisions и output fingerprints. Файловая установка выполняется через
recoverable transaction staging → verify → install → commit/rollback.

Preview и физический printer job не владеют постоянными файлами и рендерят один resolved document
напрямую в переданный `QPrinter`. Постоянными являются только явно выбранный пользователем export
и его `ReportPassport`; служебная PDF-копия не создаётся. Атомарные временные файлы имеют
application-префикс `geolog-export-`, удаляются после success/failure и могут быть очищены как
stale только для того же exact destination. Миграционная очистка старых timestamp PDF ограничена
выделенным каталогом `GEOLOG GASRATIO Pixler/Печатные копии`: каталог сначала подтверждается
ownership marker либо безопасно принимается только когда все его элементы соответствуют строгим
legacy-шаблонам. Наличие постороннего файла, symlink/reparse point или неверного marker блокирует
удаление; произвольное сканирование project directory и удаление пользовательских `*.pdf`
запрещено.

## Хранение и совместимость

- project format `v37`; 
- form schema `v17`;
- tablet layout `v25`;
- рекомендуемый рабочий проект — `.geologpkg`: versioned JSON, исходные LAS и изображения,
  manifest и SHA-256; legacy `.geolog.json` плюс content-addressed `.assets` читаются совместимо;
- запись JSON атомарная, migration последовательная;
- неизвестные данные не удаляются молча;
- credentials, tokens и исполняемый пользовательский код в проекте не хранятся.

Будущий storage port должен поддерживать manifest, column chunks, atomic commit, recovery и
совместимое чтение старого JSON. Выбор формата принимается после benchmark и crash tests.

## Производительность

Hot path проектируется с явной сложностью:

- conditioning и ratio calculations — O(N) по числу строк и O(N × C) для ограниченного числа
  газовых компонентов;
- viewport sampling — только видимый диапазон плюс небольшой context;
- cache identity основан на revision, axis, range, scale и point budget;
- нет полного digest/копирования Dataset на каждое обновление UI;
- batch acquisition и storage не выполняют O(N²) concatenation.

Benchmark должен измерять latency, scaling ratio, allocations/peak RSS и cache hit ratio. Один
быстрый synthetic test не заменяет benchmark 100k/1M/10M и реальный Windows profiling.

## Безопасность

- все внешние файлы считаются недоверенными;
- archive extraction проверяет traversal, links, count и expanded size;
- XML запрещает external entities/DTD и имеет resource limits;
- remote acquisition использует TLS/auth policy, allowlist, timeout и bounded queues;
- логи не содержат credentials, raw secrets или неограниченный payload;
- dependency lock хеширован, SBOM и security scans выполняются отдельно;
- plugin API versioned; пользовательский код при открытии проекта не выполняется.

## Расширения

Первый внешний интерфейс — read-only immutable DTO/snapshot API. Изменения разрешаются только
через validated transactional commands с permissions, timeout, audit и rollback. Multiwell, 3D
и AI workflows вводятся после storage/performance/provenance gates, а не обходят их.

## Архитектурный review для изменения

Перед merge проверяются:

1. правильный слой и направление imports;
2. единственный источник истины для нового правила;
3. immutable source и явная mutation boundary;
4. backward compatibility или migration;
5. negative/boundary/regression tests;
6. bounded CPU/memory/I/O;
7. error handling, audit и отсутствие secrets;
8. одинаковый контракт screen/preview/PDF/printer;
9. актуальность `PROJECT_PLAN.md`, `TESTING.md` и `CHANGELOG.md`;
10. отсутствие временных workflow, trigger-файлов и artifacts в дереве.

### WELL-02: числовой план обновления

`services/well_update_plan.py` строит immutable read-only DTO для новой глубины,
заполнения NaN и correction. Общая проверка схемы/оси находится в `daily_las_growth`;
разные depth domains отклоняются даже при одинаковой роли DEPTH. Локальные кривые
исключены. NaN источника не очищает значение, ноль считается измерением, infinity
и новые точки внутри сохранённой сетки отклоняются. Счётчики полные, diff ограничен
`preview_limit` (0–10000, default 200); `preview_truncated` явно обозначает сокращение.
Стоимость O(N + M*C), память O(N + M + limit), без копии Dataset. SHA-256 связывают план
с обоими Dataset. DTO сам по себе не разрешает запись.

`services/well_update_apply.py` применяет отдельный выбор нового суффикса и выбранные
показанные fill/correction cells. Выбранная correction-ячейка подтверждает точные before/after;
скрытые или подменённые ячейки отклоняются. Все новые массивы, headers и audit готовятся
до замены ссылок в Dataset; ID и объекты кривых сохраняются. Локальные кривые получают NaN
на новом участке, производные кривые становятся STALE, conditioning QC инвалидируется.
Стоимость O(N + M*C + N*C), staging O(N*C + M + 10000); полная копия проекта не нужна.

`DailyLasGrowthController` проверяет текущий LAS, сохраняет исходные artifacts и откатывает
ошибку регистрации источника. Числовой режим `DailyLasGrowthDialog` ничего не выбирает
автоматически и сбрасывает выбор при новом анализе, смене режима/файла/dataset и отмене.
`MainWindow` выполняет storage preflight и MATERIAL_AUTOSAVE через существующий backup gate;
при ошибке сохранения полный результат остаётся dirty в памяти без сообщения об успехе.
`numerical_update_history` сериализуется в project v26: источник, время, хэши до/после,
число добавленных строк и полный выбранный diff (до 10000 ячеек на операцию).
Миграция v25 → v26 добавляет пустую историю без изменения данных и ID. Частично применённый
числовой источник не считается полностью импортированным для прежнего strict append: его
новый суффикс остаётся доступен после проверки перекрытия.

`revalidate_well_numerical_update` повторяет анализ с тем же размером отображённого diff
и сравнивает весь DTO: состояния Dataset, источник, счётчики и изменения. Вызывающий код
обязан независимо проверить файл и передать актуальные имя/SHA-256, а не скопировать
их из плана. Проверка не пишет данные и не является подтверждением correction.

### Геологическое дополнение и project v27

`well_geology_update` строит неизменяемый план только свободных интервалов MD в метрах.
Профиль выбирается явно, его канонический JSON и SHA-256 определяют пространство ID
литотипов. Экспортные числовые коды уникальны в каталоге, переназначения видны в preview.
Перед применением повторно проверяются источник, профиль, числовые данные, ручные слои
и каталог. Контроллер объединяет геологию и числовые изменения одним откатом и сохраняет
исходный LAS. `geology_update_history` содержит снимок профиля и ID добавленных интервалов.
Миграция v26 → v27 добавляет пустую историю; существующие ID и данные не меняются.

### Отдельные анализы и project v28

Project v28 добавляет `Well.analysis_update_history` для immutable provenance поздних анализов
шлама. Запись хранит источник и SHA-256, выбранные поля, точный fill-only diff и хэши состояния
скважины до/после. Миграция v27 → v28 добавляет пустой well-level ledger и не связывает анализ
с произвольным Dataset. Декодирование audit fail-closed: неизвестные поля, повреждённые enum,
не-fill-only изменения и более 10000 записей/изменений отклоняются.

Чтобы изменение формата оставалось узким и проверяемым, доказанный decoder v27 заморожен в
`storage/project_codec_v27.py`. Текущий `project_codec.py` выполняет миграцию v28, строго
декодирует только новый well-level ledger и делегирует все прежние структуры v27 без изменения
их semantics, включая source artifacts, image assets и persisted projections.

### Многоязычные шаблонные блоки и project v30

Project v30 добавляет к пробе шлама упорядоченную историю вставок готовых описаний. Каждая
запись содержит уникальный ID экземпляра, ID и положительную версию шаблона и полный снимок
RU/KK/EN. Текст редактора хранится отдельно: ручные правки не разрушают provenance, а новая
версия каталога не переписывает ранее сохранённое содержание. Текущий codec делегирует старые
структуры замороженному v29; миграция v29 добавляет пустую историю без изменения описаний.

## Gas Context editor boundary

`GasContextEvent` and `GasContextRegistry` remain domain objects and contain no Qt dependencies.
`GasContextEventEditorController` is the transactional application boundary for the pre-calculation
editor: Add/Update/Duplicate/Delete mutate an immutable working registry, while `commit()` is the
only operation that replaces `Well.gas_context_events` and marks `ProjectSession.dirty`.
The Qt `GasContextEventDialog` owns presentation and input collection only; Cancel discards the
working controller without mutating the project.

This boundary deliberately does not implement Gas Ratio/Haworth/Pixler/OPUS classification rules.
The next increment consumes the persisted registry from interpretation services and export renderers,
so UI code never becomes a second source of geological classification logic.



## WITS0 alarm domain boundary

WITS-ALARM-01 starts with a Qt-independent state machine in
`services/wits0_alarms.py`. `AlarmLimits` owns threshold validation, hysteresis
and sample-count debounce. `AlarmState` is immutable and records only active or
pending side plus acknowledgement. `evaluate_alarm()` is a pure transition
function: transport cadence, widgets, audio devices and persistence are outside
this boundary.

Missing or non-finite samples cannot fabricate activation or clearing. They reset
only an uncommitted debounce sequence while an already active alarm remains active.
Acknowledgement suppresses the attention requirement but never clears the alarm;
a clear is produced only by a factual sample crossing the hysteresis recovery
boundary. Later UI/audio/marker layers must consume this state instead of
implementing a second threshold engine.

Persistence is owned by the WITS live-form settings boundary, not by the alarm evaluator. Schema v4 stores immutable `Wits0SavedAlarmRule` entries keyed by channel mnemonic and reuses `AlarmLimits` validation for min/max, hysteresis and debounce. Per-channel visual/audio policy flags are persisted beside those limits; audio defaults to opt-in while visual indication defaults on. Schema v1–v3 migrate with no configured alarms; malformed v4 rules fail closed. Runtime alarm state and acknowledgement are intentionally not persisted as configuration.


### WITS0 alarm settings presentation boundary

`ui/wits0_alarm_settings_editor.py` is a presentation-only editor for the schema-v4
`Wits0SavedAlarmRule` contract. It owns widget state and a working set of rules, delegates
threshold validation to the existing domain/persistence model, and exposes immutable saved-rule
DTOs back to `Wits0LiveViewWidget`. The live view owns form selection/save/reset orchestration.
The editor does not evaluate samples, acknowledge runtime alarms, play audio, or paint graph
markers. Those later layers must consume `services/wits0_alarms.py` rather than duplicating
threshold logic in Qt.


### WITS0 live alarm runtime boundary

`acquisition/wits0_live_alarms.py` owns runtime state for schema-v4 alarm rules. The controller
normalizes configured mnemonics and replays newly appended `AcquisitionRecordKind.DATA_ROW` records from the per-curve last processed session sequence. Repeated QWidget refreshes therefore cannot advance debounce, while a `runtime.drain()` batch containing several measurements advances debounce once per factual DATA_ROW. Policy lookup remains mnemonic-based, while runtime state and last processed sequence are keyed by `curve_id`; two curves that resolve to the same canonical mnemonic therefore cannot advance each other's debounce. Source curves consume their exact `curve_id` value from `AcquisitionDataRowPayload`. Virtual live curves consume the aligned derived value only when the DATA_ROW WITS record number belongs to the existing `source-records` provenance allowlist; no second formula or source-mapping registry is introduced. A DATA_ROW that explicitly contains a source curve with `None`, or a relevant derived row whose value is non-finite, is missing alarm input and may reset only pending debounce while an already active alarm remains active; unrelated DATA_ROW records do not break the channel sequence.

Changing a rule resets only that rule's runtime state; unchanged rules keep state across ordinary view refreshes. Runtime evaluation reads the append-only acquisition session rather than the frozen plot row boundary, so Pause affects visualization but does not suspend alarm monitoring. Rebinding to another acquisition runtime clears all runtime alarm state.
Acknowledgement delegates to the Qt-independent `acknowledge_alarm()` transition and never clears
the active side. `Wits0LiveViewWidget` passes the full dataset row count and current virtual-curve projection to the controller and renders the resulting immutable statuses; dashboard/table presentation must not recalculate thresholds. In addition to current status, the controller retains a bounded factual event history for active-side changes. Events are derived from the before/after active state rather than the single summary transition, so a direct HIGH→LOW crossing records HIGH clear and LOW activation separately. Historical events carry dataset row, acquisition sequence, factual value and threshold plus visual/audio policy flags; seeding a newly applied rule from an already existing current value does not fabricate a historical event.

Audio and graph presentation are downstream consumers of that event history. The live widget coalesces all audio-enabled activations produced by one evaluation batch into one system cue, so repeated refresh does not replay sound. Visual-enabled activation/clear events are converted to `THRESHOLD_ALARM` markers through the public read-only `AcquisitionLiveView.axis_value_for_row()` lookup. Alarm markers have priority inside the bounded marker budget. Pause continues runtime evaluation/audio but excludes post-pause rows from the frozen projection; those retained events become visible on Resume. No audio or marker layer evaluates thresholds independently.


## LAS import performance observability boundary

Large-LAS profiling reuses the existing application logging boundary and does not introduce a
parallel profiler service. `services/process_metrics.py` provides a dependency-free best-effort
process memory snapshot: current RSS where the platform exposes it cheaply and process peak RSS.
Unsupported/error paths return `None` metrics and must never make an import fail.

`data/las_adapter.py` remains the parser/materialization owner. Its existing
`las.import.performance` event keeps the source/parse/dataset/report/total timing contract and
adds RSS checkpoints for those same boundaries. `services/import_jobs.py` measures the
application stages `job_load`, `policy`, `review`, `register` and total, while failures
record the exact diagnostic stage. `MainWindow._present_imported_dataset_safely()` owns only the
final presentation metric and keeps the existing recovery workspace unchanged.

Performance telemetry is deliberately metadata-only: basename, byte/row/curve/warning counts,
encoding, durations, RSS and exception type. Source values and full filesystem paths are not
logged. These measurements are diagnostic evidence for PERF-07/PERF-05 decisions; they are not
wall-clock pass/fail thresholds by themselves.


## Presentation refresh coalescing boundary

`services/presentation_refresh.py` defines a Qt-independent typed accumulator for cheap
presentation-only refresh intents. It does not mutate project state, Dataset objects, TabletLayout,
history, or widgets and owns no timer. A consumer may merge repeated intents and later consume one
immutable batch with the original request count.

The first consumer is deliberately narrow. `MainWindow` uses one single-shot 75-ms timer only for
the secondary Project Tree and window-title updates produced by track-width and track-order drag
signals. The layout mutation itself remains synchronous; track-width rendering continues through
the existing `DirtyReason.STATIC` partial TabletView path, and drag-order visual feedback remains
owned by TabletView. The timer is not restarted for every request, which bounds staleness while
reducing repeated tree rebuilds during a continuous gesture.

Dataset replacement, imports, Undo/Redo callbacks, axis conversions, report refresh, and full
TabletView rebuilds remain outside this coalescer. Extending the intent set requires a measured hot
path plus a regression proving that delayed presentation cannot expose stale domain state.


## Visible-depth incremental refresh boundary

Visible-depth navigation is a viewport mutation, not a TabletLayout topology mutation.
`TabletView._apply_visible_depth()` already updates plot Y ranges, shared rulers, visible-curve
LOD data, geology overlays, lithology/stratigraphy text visibility and annotation anchors in place.
A manual depth-range change therefore must not call the generic `MainWindow._layout_changed()`
full-rebuild path after `TabletView.set_visible_depth()`.

Reset keeps the existing semantic contract: the controller clears the saved range and one
`TabletView.refresh_view()` resolves the default/recommended initial window. MainWindow updates
only title/log state afterwards. Neither manual range changes nor reset rebuild Project Tree,
because the explorer contains project/well/dataset/curve/track structure but no viewport-depth
state.


## Curve-metadata history incremental refresh boundary

Curve metadata Undo/Redo mutates metadata inside the current Dataset; it does not replace the
Dataset or TabletLayout. Therefore `MainWindow._after_curve_metadata_history_change()` must not
call the full `_show_current_dataset()` render path. That path destroys and recreates every
PyQtGraph `PlotWidget` and was reproducibly associated with Windows native access violations in
isolated history tests.

`TabletView.refresh_dataset_metadata()` owns the incremental reconciliation. It preserves existing
track widgets, reconciles rendered curve membership against current mnemonics when metadata rename
changes lookup identity, and applies `DirtyReason.STYLE` so display names, units, ranges and curve
headers are rebuilt in place. MainWindow refreshes the curve view, LAS table, curve browser,
interpretation-report presentation, Project Tree and dirty title without replacing the tablet
widget tree. A different Dataset ID still falls back to the existing full dataset replacement.

Печатный visual profile применяется также в geological `interpretation_report_html`
(и его QTextDocument PDF), `interpretation_report_office` XLSX, общих DOCX styles/table
helpers и simple tablet header/footer. Размеры Word переводятся из points в half-points;
Excel сохраняет числовые типы. Shared defaults относятся к presentation; пользовательские
Masterlog element properties и source/candidate/domain values не переписываются.

Geological `interpretation_report_office` table worksheets keep their authored column widths and
print at A4 landscape / 100% with horizontal continuation pages. Row 1 and column A are repeated
as print titles, the wrapped header reserves a readable minimum height, and canonical brand/page
footer fields are repeated without converting numeric cells to text. This mirrors the generic
Data/Parameters pagination policy instead of introducing a second fit-to-one-page rule.

`printing/report_document_control.py` строит immutable localized groups control/context/approvals
из cleaned `InterpretationReportIdentity`. Date row добавляется только из непустого user field;
generation audit не является входом. PDF и polished DOCX cover адаптируют один snapshot; readable
XLSX добавляет available rows на отдельный лист с тем же visual profile. Workspace выбирает
сохранённые headers через language + report-profile resolver. Project schema v37 не меняется.

Masterlog document-control fields зарегистрированы в `printing/header_fields.py`. Значения
хранятся в существующем `MasterlogTemplate.properties["header_fields"]`, отдельно для каждой
формы; они не входят в паспорт скважины и не наследуют LAS metadata. Resolver возвращает
пустую строку для отсутствующих реквизитов, поэтому preview/PDF не печатают placeholder
или автоматически созданную дату. Геометрия и подписи пользовательской шапки задаются редактором.

Generic report export controller assembles `ReportDocumentControl` from session context and
an explicitly bound `masterlog-template` revision. A missing or changed revision raises
`ReportDefinitionError` before the output transaction writes. Adapters consume the immutable
snapshot without resolving curves or reading session state; resolved indices remain authoritative.
HTML uses a normal-flow footer; DOCX packages a related footer part with PAGE/NUMPAGES fields.
Shared `compact_report_footer` bounds each repeated value to 48 characters; full values stay
in the document-control zone. Both adapters use the canonical visual profile.

`data/report_document_control_excel.py` is the shared XLSX presentation adapter for generic
and interpretation snapshots. Generic resolved Excel passes the same controller snapshot
as HTML/DOCX; the low-level selection exporter accepts an optional snapshot and preserves
its existing sheet/data contract when omitted. Spreadsheet safety is applied to every
presentation row. Data/Parameters print styling reads the immutable visual profile.

Wide Data/Parameters worksheets use A4 landscape at 100% with horizontal pagination
and repeated key columns, rather than fitting every column into one page. Document
control remains fit-width on A4.

`printing/form_report_document_control.py` resolves a shared form/session snapshot for generic
Office and Masterlog. `masterlog_document_control.py` enables an automatic band only when at
least one saved document-control field is nonempty. It reserves the maximum localized row
count for language-independent pagination. The band is added below the custom header; a
10 mm footer is excluded from column geometry. One job snapshot retains the selected whole
interval on every depth/column page. Partial final pages retain physical depth scale. Text is
searchable PDF text, elided and clipped to the band/footer. Legacy forms without control
metadata retain their geometry; source arrays and custom header coordinates are unchanged.

Standard interpretation PDF chart panels retain `HydrocarbonCandidateInterval` objects to the
paint boundary instead of collapsing them to depth tuples. Candidate bands use the shared
`FluidMarkerSpec`; the final chart column adds shape + short code at the interval midpoint.
This is a presentation-only grayscale safeguard: depth, hypothesis, evidence, calculations,
and source curves remain untouched. Enhanced/OPUS charts already use the same marker contract.

The interpretation PDF/system-print renderer resolves one `ReportDocumentControl` snapshot
into `PageCanvas`. `compact_report_footer` provides the repeated document/revision/status/
confidentiality text; date and audit timestamps are excluded. Nonempty details reserve an
additional 14 points beyond the existing 16-point footer. Brand/page number use measured
separate widths; each string is elided and the footer is clipped. Painter state is restored.
Fonts compensate device DPI because the canvas already scales painter coordinates from
points. Empty metadata retains existing content geometry; no persisted schema changes.

When footer reservation reduces the chart budget, the full-report chart renderer defers an
overflowing geology legend to pages after the charts and draws an explicit reference on
chart pages. Shared legend pagination preserves complete rows and every symbol. HIDE
remains authoritative. The methodology still precedes charts; no catalog is inserted before it.

`printing/report_document_control_docx.py` serializes one shared Word footer from an
optional immutable control snapshot and output language. A fixed-layout percentage-width
table separates canonical brand and PAGE/NUMPAGES; optional details are bounded to 96
characters, with explicit row heights and a one-point trailing paragraph. Section margins
reserve at least the full footer height. Both portrait-cover and landscape-body sections
explicitly reference the same footer part without page-number restart. Ordinary interpretation
uses brand/numbering only; polished rewrite substitutes form-owned control metadata while
preserving the base package relationships and classification audit. Generic DOCX delegates
to the same adapter. Date/audit timestamps are excluded; full values remain in body/cover.

The interpretation package explicitly relates styles.xml as well as the footer and audit parts,
so Word can apply the shared body styles rather than relying on built-in style names.

`data/hydrocarbon_interpretation_export_docx_polished.py` также не владеет собственной
палитрой: при сериализации cover/narrative/table OOXML он разрешает
`modern_oilfield_report_profile()` и отображает semantic roles профиля в Word colours,
half-point typography, borders и fills. Footer остаётся отдельным shared adapter, поэтому
визуальная система и document-control contract развиваются независимо и не дублируют источник истины.

`printing/masterlog_renderer.py` использует тот же `ReportVisualProfile` только для
renderer-owned neutral chrome: page background, structural borders, grid, headings, neutral
text/service fills и missing-asset/error placeholders. Explicit colours сохранённого header
template, lithology/stratigraphy/LBA domain encoding, curve styles и annotation/callout style
contracts остаются отдельными источниками истины и не подменяются profile palette. Это позволяет
менять общую печатную систему без миграции форм, геологии или пользовательских стилей.
Masterlog header defaults consume `modern_oilfield_report_profile()` at render time:
page/frame roles, default text/line/image-slot colours, body/caption/table typography and
physical rule weights. Point sizes convert to millimetres before the existing painter
transform; the profile does not mutate persisted form properties. Explicit valid saved
colour/background/font/line-width overrides retain precedence. Lithotype/LBA semantic
swatches and intensity geometry remain domain-owned, including grayscale profile tests.
The same header-element painter serves reusable tablet headers and full Masterlog output.

Masterlog column legends resolve the same mapped CurveData and MasterlogCurveStyle as
curve painting. `_curve_uses_point_presentation` shares source/canonical identifiers between
the key and plot; `_MASTERLOG_CURVE_PEN_STYLES` shares line style mapping. A clipped key lane
precedes the label, which retains the resolved numeric range and appends the bound channel's
unit. Missing curves retain their mnemonic label without a fabricated key or unit. This
render-only adapter does not mutate templates/data or change the ratio presentation policy.

Masterlog column frames, grid and depth labels consume the shared visual profile. Grid
major rules convert thin_rule_pt to millimetres, minor rules use half that weight; saved
alpha and minor alpha factor remain intact. Five-metre depth coordinates and grid visibility
are unchanged. Depth labels use table_pt through the existing transform-aware font helper.

`printing/gas_context_track.py` is a render-only adapter over `GasContextRegistry`. Boundary
splitting resolves each segment with the existing registry priority and merges adjacent pieces
of the same event; point events keep their true depth. Only confirmed, customer-visible context
is drawn. Shared code/localized label/neutral border styles serve standard/enhanced PDF and
whole-well PNG preview. A reserved track protects curve/fluid lanes; long IDs wrap in the
complete event legend, which paginates independently of plot depth. No domain/schema/data
mutation or replacement candidate/exclusion policy is introduced. Font size compensates the
paint device DPI so new context text keeps physical point sizes.

`services/gas_context_report_labels.py` owns the Qt-free event code/type/impact/identity-label
contract used by the existing print-track adapter and all client-table exporters. HTML and
DOCX add identity text in the existing type cell to preserve table geometry; XLSX retains
the existing 17-column schema and Event ID in column Q. Only presentation strings change:
raw enum persistence, event selection, numeric/QC values and classification audit remain
domain-owned. The report service does not import a Qt/printing adapter to resolve labels.

The shared interpretation geology-legend painter now resolves neutral chrome and caption/table
sizes from `ReportVisualProfile`. Measurement and painting use the same font helper: paged
paint devices render point coordinates with device-DPI compensation, while PNG retains its
pixel-coordinate contract. Catalog geology colours/patterns and LBA symbols remain semantic
inputs; only renderer-owned page/text/border roles use the report palette. Existing bounded
ellipsis, full-symbol pagination and immutable geology/source snapshots remain authoritative.

Interpretation PDF chart adapters resolve one immutable palette snapshot per painter function. Page/header fills, neutral text and structural strokes use semantic roles; curve series, fluid classifications and ratio reference colours retain their existing contracts. This palette slice does not alter geometry, typography or stored styles.

`report_painter_fonts.point_coordinate_font` validates positive finite sizes and compensates device DPI only for paged painters using physical point coordinates. Interpretation headings opt into that contract explicitly; legacy pixel callers retain their old sizing. Geology legends reuse the adapter. Chart-owned grids/ticks/frames resolve shared thin/half-thin/strong rules without changing semantic curve/reference/candidate pens. Ratio headers reserve their internal scale-label band independently of wrapped heading height.

All font calls owned by standard/enhanced interpretation PDF chart adapters now use `point_coordinate_font`. This removes repeated device-DPI scaling for narrative, numeric and marker text without changing source values, colours or classification. Depth numbers and normalized percentages use shared table/caption typography; narrative and narrow ratio/marker sizes retain their existing 72-DPI budgets. Qt font quantization is reflected in the actual physical-output regression, rather than hidden by a broad tolerance.

Interpretation source curves and ratio-reference traces use non-cosmetic physical-point pens (1.25/0.7 pt); real PDF stroke-width/dash regressions at 72/300/600 DPI prevent high-resolution washout while retaining source values, colours and geometry.

Ratio-scale PDF headings отделены в `ratio_scale_heading`: один point-coordinate metric contract задаёт header reservation и caption-size paint. Endpoint-first label selection ограничивает коллизии без изменения fixed ratio scales, grid ticks и source/reference geometry; shared Wh/Bh lane получает одну шапку.

`interpretation_note_layout` измеряет wrapped explanatory caption в point coordinates на целевом paint device. Оба PDF adapters передают measured note height в depth-page budget и `chart_geometry`; default/minimum 28 pt сохраняет совместимость остальных callers. Forced-empty geology labels используют caption role. Candidate-present marker legends остаются отдельным contract.
