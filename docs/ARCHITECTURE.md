# Архитектура

Актуально на 23 июля 2026 года.

## Модель

Проект — desktop-модульный монолит на Python 3.11, PySide6, PyQtGraph и NumPy.

```text
UI / tablet / printing
          ↓
application controllers and services
          ↓
domain models and contracts
          ↑
storage / importers / plugins
```

`domain` не должен зависеть от Qt, файлового диалога или конкретного формата. UI собирает
ввод и отображает read models; изменяющая операция проходит через controller/service и
помечает session dirty. Импортёр преобразует внешний формат в доменную модель и не меняет
источник.

## Пакеты

```text
src/geoworkbench/
├── app/               запуск приложения
├── calculations/      формулы и расчётные профили
├── catalogs/          справочники и семантика параметров
├── data/              dataset и LAS-ориентированные структуры
├── domain/            модели без UI
├── form_constructor/  ресурсы и модель конструктора
├── forms/             формы и шаблоны
├── importers/         внешние форматы
├── plugins/           версионированные контракты расширения
├── printing/          print jobs, PDF и Masterlog renderer
├── project/           controllers и project session
├── services/          прикладные операции
├── storage/           codec, migrations и atomic JSON
├── tablet/            layout, interaction и графическое представление
├── ui/                окна и диалоги PySide6
└── visualization/     независимые модели визуализации
```

## Граница импортных jobs

`services/import_jobs.py` содержит стабильные типы источников, маршрутизацию и единый
`DatasetImportJobExecutor`. Qt-слой выбирает файлы, собирает подтверждение пользователя и
показывает результат, но не вызывает LAS-парсер и не присоединяет импортированный dataset к
проекту напрямую. Executor выполняет CSV/Excel планы, применяет strict/compatible/manual
политику LAS, сохраняет lossless source document и import report, а также регистрирует результат
Paradox через один project-session port.

Paradox чтение и преобразование остаются отменяемой фоновой операцией диалога; после успешного
результата commit в проект выполняется только через import-job boundary. Отклонённый, отменённый
или ошибочный файл не создаёт частично зарегистрированный dataset.

## Граница print jobs

`services/print_jobs.py` содержит `PrintJobExecutor`, который владеет конфигурацией
`QPrinter`, физическим рендерингом, PDF и постраничным raster/SVG export. Qt-слой выбирает
источник и назначение, открывает системные диалоги, подтверждает перезапись и показывает
результат, но не вызывает функции renderer/export напрямую.

## Session binding и workspace-команды

`SessionBindingController` хранит единый реестр session-aware компонентов. После открытия
проекта он согласованно перепривязывает 27 контроллеров и запускает их reset hooks для Undo/Redo,
выделений и незавершённых режимов редактирования. Это исключает продолжение операций со старой
`ProjectSession`, включая TIME↔DEPTH и LAS range workflows.

`WorkspaceCommandController` проверяет payload дерева проекта, разрешает well/dataset context
и только затем вызывает UI-port для отображения curve, track, lithology, stratigraphy или
interpretation. Qt-обработчик дерева не присваивает `current_well_id` и `current_dataset_id`
напрямую; некорректная команда не оставляет частично изменённый контекст.

## Граница изменения сериализуемой модели

`MainWindow` и диалоги собирают ввод, но commit выполняют через project/tablet controllers.
`TabletLayoutMutationController` содержит Qt-независимые операции ширины, порядка, вертикального
индекса и видимого диапазона. В основном приложении жест сначала отправляет синхронный request
в `TabletController`; локальный mutation-controller используется как детерминированный fallback
для standalone view и внутренней нормализации.

`DerivedDatasetController` создаёт checkpoint перед merge/external-LAS copy и выполняет rollback
всех dataset, появившихся после checkpoint, вместе с layout/source/import-report sidecars. Затем
он восстанавливает исходные well/dataset selection и `dirty`. Batch project images устанавливаются
только через `MasterlogTemplateController.install_image_assets`, который сначала валидирует весь
набор и не допускает частичного commit при конфликте.

## Хранение и совместимость

- текущий JSON-формат проекта — 18;
- текущий формат layout планшета — 14;
- миграции выполняются последовательно и не должны удалять неизвестные данные молча;
- исходные LAS и импортированные assets идентифицируются fingerprint/SHA-256;
- сохранение JSON атомарное; внешние абсолютные пути не являются переносимой частью проекта;
- credentials, tokens и исполняемый пользовательский код в проекте не хранятся.

## Планшет

Layout является декларативной моделью треков, кривых, шкал, сеток и видимости. Общая ось
Y синхронизирует треки; X остаётся независимой. Экран виртуализирует видимый диапазон.
Аннотации и интервалы хранят каноническую привязку к dataset/form scope, а экранная
геометрия вычисляется из неё.

Текущий риск: `tablet_view.py` объединяет lifecycle треков, event routing, навигацию,
редактирование, аннотации и часть orchestration. Целевая граница разделяет их на отдельные
контроллеры с Qt-независимыми state transitions.

## Единая ReportDefinition

`services/report_definition.py` содержит immutable schema v1 и Qt-независимый resolver.
Definition фиксирует report profile, dataset/index ID, sections, curve IDs, language, form
revision и interval mode `full/current/custom/selection`. Resolver не переключает индекс
молча: он проверяет точный ID, ограничивает диапазон фактическим доменом, создаёт один
inclusive массив строк и возвращает `ResolvedReportDefinition`.

Print Center замораживает viewport/full/selection context при открытии диалога. Preview и
итоговый printer/PDF/page-export job получают один resolved range, после чего pagination
нормализуется в точный custom interval. Планшет использует выбранный `vertical_index_id`;
DEPTH-selection не предлагается для TIME-view. Masterlog preview/PDF/system preview и
выбранный CSV/XLSX экспорт используют тот же контракт. Report Passport сохраняет canonical
payload definition и его SHA-256.

Qt-независимый `services/interval_selection.py` содержит расчёт строк глубинного интервала;
`DatasetIntervalSelection` остаётся UI-observer, но exporter больше не импортирует Qt только
ради геометрии диапазона. Текущий project format v20 дополнительно хранит operational events, acquisition sessions, lag correction profiles и независимый append history каждого dataset.

## Печать

Печатный renderer работает в миллиметрах и не является снимком экрана. Одна модель формы
питает preview, PDF и системный принтер. `PrintJobExecutor` является единственной прикладной
точкой запуска printer/PDF/page-export jobs, а UI отвечает только за взаимодействие с
пользователем. Grid settings, axis divisions, header, legends, lithotypes и annotations
обязаны использовать те же сериализуемые настройки.

`ReportPassport` реализован как headless application service. Он строит канонический JSON без
времени генерации и абсолютного пути вывода, подписывает его SHA-256 и фиксирует source
fingerprints, точный интервал и выбранные значения, полный semantic binding/UOM, версии формул,
content-addressed form/template revision, locale и render options. Файловые экспорты сохраняют
`<имя>.<формат>.passport.json`; schema v4 содержит fingerprints уже сформированных output-файлов,
а загрузчик проверяет digest JSON, размер и SHA-256 каждого artifact.

`services/report_output_transaction.py` владеет recoverable filesystem transaction schema v1.
Renderer пишет в staging, transaction журналирует backup/install/delete operations, устанавливает
output и sidecar, повторно проверяет fingerprints и только затем фиксирует `committed`. Состояния
до commit откатываются, committed-состояние после сбоя завершает только cleanup.


`printing/print_layout.py` является Qt-независимым источником истины для media schema v1:
A4/A3/custom/roll, Fit/100%, physical 96-DPI mapping и overlap. `PrintDocumentPlan` строит
декартово произведение vertical pagination и horizontal continuations. `page_renderer` и
`tablet_print` получают уже разрешённый continuation slice; UI не вычисляет clipping самостоятельно.

`printing/printer_gate.py` принимает нормализованный `PrinterCapabilities` snapshot. Qt-adapter
после `QPrintDialog` повторно применяет собственный page layout, переводит minimum margins в
миллиметры и проверяет state, supported media, custom bounds, printable area, DPI и выбранный
page range. Gate errors блокируют `QPainter.begin`; warnings остаются в result/log. Report Passport
schema v4 подписывает scale/continuation settings и fingerprints готовых файлов.

`RenderGolden` schema v1 фиксирует геометрию до платформенного raster-layer: Qt-независимые
`grid_geometry`, `lithology_pattern_catalog` и `annotation_layout` формируют canonical JSON,
а два составных SVG дают визуальный screen/print эталон. Masterlog и экранные адаптеры используют
эти общие функции, поэтому изменение division, legend resolution, bitmap identity или annotation
leader требует явного обновления golden и объяснения изменения.

## Данные и индексы

Dataset может иметь MD, TVD, TVDSS, относительное или абсолютное время; active index не
удаляет остальные колонки. TIME→DEPTH не считается однозначным без явной политики.
Неизвестная единица не конвертируется молча. Реализованный `SemanticChannelDictionary`
использует существующий Sensors-каталог как источник vendor aliases и sensor IDs, а
`UomDictionary` нормализует только явно известные единицы по quantity class. Каждая кривая
хранит сериализуемый `SemanticChannelBinding`: canonical kind/mnemonic, quantity class,
canonical/source UOM, aliases, sensor/source, исходную мнемонику, confidence, matched-by и
evidence. Формат проекта v19 сохраняет binding, введённый в v16, поэтому новый каталог не меняет смысл уже подтверждённого проекта. `build_import_review()` формирует read-only модель диагностики.
`ImportReviewController` владеет plan/preview/commit на глубокой копии, а Qt-диалог только
редактирует план. `DatasetImportJobExecutor` передаёт project-session port исключительно
подтверждённую копию; отмена не изменяет коллекции проекта и `dirty`.

## Real-time boundary

Real-time развивается отдельным адаптером: append-only growing dataset и recorded replay уже
зафиксированы; versioned lag/depth correction также завершена; далее идут offline WITSML 2.1 inventory/fixtures →
secured ETP 1.2. Measurement time и arrival time хранятся
раздельно. Gap, duplicate, out-of-order, stale и calibration являются данными QC, а не
только строками журнала. Lag/depth correction создаёт версионированное преобразование и
не переписывает acquisition source.


## Граница versioned lag/depth correction

`domain/lag_correction.py` определяет immutable schema v1 для профиля, непрерывных revisions,
метода, параметров и source/corrected axis. `services/lag_correction.py` является единственной
доменной mutation/verification boundary: она материализует новый `DatasetKind.DERIVED`, подписывает
source prefix и output, проверяет formula/acquisition provenance и не меняет source dataset либо
append-only journal. Каждая revision владеет отдельным output dataset.

`project/lag_correction_controller.py` связывает операции с `ProjectSession`, optimistic guards и
`dirty`; Qt-диалог только собирает ввод, показывает preview и выбирает проекцию. Source/corrected
axis переключается через active index derived dataset. `ReportDefinition` фиксирует dataset/index
явно и не пересчитывает коррекцию при экспорте.

Project format v19 добавляет `Well.lag_correction_profiles`; миграция `v18 → v19` создаёт пустую
collection. Codec повторно материализует каждую revision при загрузке и блокирует source/output
divergence, unknown fields и разрывы revision sequence.

## Plugin and automation boundary

Внутренний registry и контракты не означают автоматическую загрузку произвольного кода.
Будущий API сначала read-only; изменяющие команды работают транзакционно, журналируются и
требуют явного запуска. Проект никогда не выполняет вложенный скрипт при открытии.

## Обязательные инварианты

- исходный файл не перезаписывается скрытно;
- `eval`, `pickle` и неограниченное исполнение шаблонов запрещены;
- UI не обходит controller при изменении project state;
- экран, PDF и printer используют одну семантику формы;
- ноль, пропуск и отсутствующий канал различаются;
- любой расчёт сохраняет входы, единицы, версию и provenance;
- safety-critical выводы не заявляются: приложение является decision-support tool.

Текущие нарушения и план декомпозиции: [PRODUCT_AUDIT_2026.md](PRODUCT_AUDIT_2026.md).

## Граница DOCX/HTML export

`data/report_document_export.py` принимает только готовый `ResolvedReportDefinition` и не
вызывает resolver повторно. `ReportDocumentModel` schema v1 содержит metadata, coverage и
строки точного resolved interval. DOCX и HTML являются двумя сериализаторами одной модели:

- DOCX — deterministic OOXML package стандартной библиотекой, без макросов, external links и
  новой обязательной зависимости;
- HTML — self-contained UTF-8 document с inline CSS, без scripts и network resources.

Qt-слой выбирает путь и формат. `DatasetExportController` передаёт dataset и resolved report
адаптеру. Финальный файл никогда не устанавливается напрямую: producer пишет в staging,
`ReportOutputTransaction` рассчитывает fingerprint, финализирует Passport schema v4 и атомарно
фиксирует output + sidecar. Project format v19 хранит operational events, acquisition sessions и lag correction profiles; ReportDocumentModel остаётся отдельным runtime contract.

## Граница operational events

`domain/operational_events.py` определяет immutable schema v1: discriminator kind, typed payload,
depth/time anchors, canonical UTC timestamps, source, revision, calibration и QC flags.
`Well.operational_events` — сериализуемый объект `event_id → event`, введённый в project format v17 и сохраняемый в текущем v19.

Изменение коллекции разрешено только через `OperationalEventController`. Он проверяет well
identity и expected revision, затем пересчитывает QC полной коллекции. UI/import code не должен
писать в словарь напрямую.

`OperationalEventQcEvaluator` не использует Qt, порядок dictionary или текущее системное время.
Пороговые значения передаются через immutable policy. Поэтому одинаковая persisted collection
даёт одинаковые duplicate/out-of-order/gap/stale/calibration flags.

`resolve_operational_event_report()` является projection adapter над уже готовым
`ResolvedReportDefinition`. Он не вызывает interval resolver и не переключает индекс скрытно.
Depth, relative-time и datetime indexes используют только соответствующий event anchor.

## Граница append-only acquisition

`domain/acquisition.py` определяет acquisition schema v1: immutable dataset schema, contiguous
records, checkpoints и controlled-close metadata. `Well.acquisition_sessions` введён в
project format v18 и сохраняется в v19; миграция `v17 → v18` добавляет пустую collection без изменения datasets/events.

`AcquisitionController` является единственной mutation boundary. Он использует bounded pending
buffer, проверяет sequence/schema, атомарно применяет row/event record и при ошибке восстанавливает
dataset, operational events и source journal. Growing dataset не заменяет строки и не меняет
первичный source record.

Checkpoint подписывает row count, dataset projection, event/QC projection и combined audit digest.
`replay_acquisition_session()` воспроизводит журнал с начала либо продолжает только после verified
checkpoint; divergence блокирует результат. Производная lag/depth boundary реализована отдельно и
не меняет append-only source.
