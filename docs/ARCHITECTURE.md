<!-- runtime-contract: package=0.7.93; project=v22; form=v13; layout=v22 -->
# Архитектура

Актуально на 2 августа 2026 года.

## Архитектурный стиль

GEOLOG GASRATIO@Pixler — desktop-модульный монолит на Python 3.11, PySide6, PyQtGraph и NumPy.
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
├── app/               запуск и будущий composition root
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

Целевая сборка приложения — один `ApplicationContext`, создаваемый в `app`. Он владеет storage,
semantic/UOM catalogs, import/report factories, credentials и audit services. Feature coordinators
получают только нужные ports. `MainWindow` постепенно остаётся shell/composition UI, а не местом
бизнес-логики.

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

Исходный LAS/GS2/raw artifact, source mnemonic, unit, mapping evidence и fingerprint являются
доказательствами происхождения. Производная кривая не подменяет source-кривую и получает
versioned provenance. Экспорт является проекцией проекта и не заменяет `Ctrl+S`.

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

### Следующая граница

Правило определения короткого gap пока представлено в calculation conditioning и в старом
render sampling. Следующий безопасный рефакторинг вынесет общий immutable continuity policy и
segment mask в Qt-независимый нижний слой. До этого calculation pipeline является источником
истины для derived curves, а render policy не имеет права изменять Dataset.

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

## Импортные jobs

`services/import_jobs.py` маршрутизирует стабильные source types в единый
`DatasetImportJobExecutor`. Qt выбирает файл, собирает подтверждение и показывает результат.
Executor выполняет bounded read/parse, semantic mapping, import report и атомарную регистрацию.
Отмена, отказ validation или exception не оставляют частично добавленный Dataset.

LAS/XML/adapters обязаны ограничивать bytes, elements, nesting, text, attributes, allocations и
время до materialization. DTD/external entity и недоверенные пути запрещены.

## Планшет и rendering

`VerticalRulerLayout` является единственным источником глубинных/временных отметок для всего viewport или печатной страницы. `VerticalRulerScaleSettings` задаёт общую частоту, а `VerticalRulerTrackSettings` может только скрывать ось, подписи или часть общего набора рисок. Колонка не рассчитывает собственный шаг, значения или Y-координаты. Контракт сохраняется в tablet layout v22; старые layouts мигрируют к automatic/visible defaults.

`TabletLayout` — декларативная сериализуемая модель треков, bindings, шкал, сеток и видимости.
Общая вертикальная ось синхронизирует треки; X независим. Экран виртуализирует viewport, а
geometry cache хранит только производную геометрию, не source arrays.

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

`ReportPassport` сохраняет канонический payload, source fingerprints, semantic bindings, версии
формул, form/template revisions и output fingerprints. Файловая установка выполняется через
recoverable transaction staging → verify → install → commit/rollback.

## Хранение и совместимость

- project format `v22`;
- form schema `v13`;
- tablet layout `v22`;
- текущий проект — JSON плюс content-addressed `.assets`;
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
