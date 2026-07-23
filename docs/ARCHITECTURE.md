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
проекта он согласованно перепривязывает 26 контроллеров и запускает их reset hooks для Undo/Redo,
выделений и незавершённых режимов редактирования. Это исключает продолжение операций со старой
`ProjectSession`, включая TIME↔DEPTH и LAS range workflows.

`WorkspaceCommandController` проверяет payload дерева проекта, разрешает well/dataset context
и только затем вызывает UI-port для отображения curve, track, lithology, stratigraphy или
interpretation. Qt-обработчик дерева не присваивает `current_well_id` и `current_dataset_id`
напрямую; некорректная команда не оставляет частично изменённый контекст.

## Хранение и совместимость

- текущий JSON-формат проекта — 15;
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

## Печать

Печатный renderer работает в миллиметрах и не является снимком экрана. Одна модель формы
питает preview, PDF и системный принтер. `PrintJobExecutor` является единственной прикладной
точкой запуска printer/PDF/page-export jobs, а UI отвечает только за взаимодействие с
пользователем. Grid settings, axis divisions, header, legends, lithotypes и annotations
обязаны использовать те же сериализуемые настройки.

Целевая `ReportPassport` фиксирует source fingerprints, dataset/form IDs, bindings, UOM,
формулы, интервал, locale, template revision и render options. Это делает отчёт повторяемым
и объяснимым.

## Данные и индексы

Dataset может иметь MD, TVD, TVDSS, относительное или абсолютное время; active index не
удаляет остальные колонки. TIME→DEPTH не считается однозначным без явной политики.
Неизвестная единица не конвертируется молча. Целевой Semantic Channel Dictionary хранит
canonical kind, quantity class, UOM, aliases, sensor/source и исходную мнемонику.

## Real-time boundary

Real-time развивается отдельным адаптером: WITSML 2.1 inventory → recorded replay →
append-only growing dataset → secured ETP 1.2. Measurement time и arrival time хранятся
раздельно. Gap, duplicate, out-of-order, stale и calibration являются данными QC, а не
только строками журнала. Lag/depth correction создаёт версионированное преобразование и
не переписывает acquisition source.

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
