# Проверка версии 0.7.16 — GeoScape/Paradox DB

Дата: 22 июля 2026

## Автоматические проверки

- Paradox/SQLite/неизвестный/пустой формат;
- схема, записи, NULL, числовое декодирование и чтение комплекта;
- исходники открываются только для чтения и сохраняют SHA-256;
- глубина, время, неоднозначность и ручная замена индекса;
- единая `Dataset`-модель, неизвестные каналы и исходное числовое время;
- профиль с точной сигнатурой, пользовательский словарь и правила повторяющейся глубины;
- TIME → DEPTH и пакетные правила имени/перезаписи;
- временной индекс разрешён планом LAS 2.0;
- версия пакета, компиляция и синхронность RU/KK/EN.

Доступный без GUI набор: `119 passed`. `BLData.db` прочитан как 3488 записей/70 полей, `D250.db` — 1739/101. Критических ошибок нет, все выбранные исходные поля представлены в `Dataset`, контрольные суммы DB/PX/TV/FAM не изменились.

В контейнере отсутствуют `PySide6`, `pyqtgraph` и `lasio`. Поэтому полный Qt/offscreen-прогон, физическая печать и фактический цикл `DB → LAS → текущий LAS-reader` здесь не выполнены. Экспорт и повторное открытие встроены в пакетный сервис и должны быть подтверждены в штатной Windows-среде.

## Ручной smoke-test

1. Перетащите `BLData.db` и проверьте автоматическое обнаружение PX/TV/FAM.
2. Подтвердите `S113` как глубину и `S0` как время; проверьте первые/последние 20 строк.
3. Откройте результат в редакторе, измените мнемонику/единицу, постройте глубинный и временной графики.
4. Сохраните глубинный LAS и временной LAS; повторно откройте оба текущим LAS-reader.
5. Откройте `D250.db`: окно должно показать неоднозначные кандидаты и потребовать ручной выбор (`S101`, `S115`, `S108` и др.).
6. Проверьте профиль, пользовательский словарь, отмену, пакетный конвертер, защиту от перезаписи и JSON-журнал.
7. Сравните SHA-256 исходников до и после работы; значения должны совпадать.

# Проверка версии 0.7.15 — профессиональный слой аннотаций

Дата: 22 июля 2026

## Автоматические проверки

- сериализация полной модели аннотации и обратная совместимость с `depth_annotation`;
- сохранение геометрии, стиля, блокировки и флага печати;
- сохранение значения кривой как редактируемой печатной метки;
- привязка объекта к конкретной дорожке;
- сохранность аннотаций при создании объединённого LAS, Undo и Redo;
- прямой рендер Masterlog и исключение объектов с `print_enabled=false`;
- синхронность ключей локализации RU/KK/EN;
- компиляция `src` и `tests` через `compileall`.

Результат доступной в контейнере проверки: `79 passed`. В набор вошли модель и история
аннотаций, сращивание LAS, формат проекта, image assets, миграционная совместимость,
статические интеграционные контракты и нормализация текста. Все три словаря содержат по
`1287` одинаковых ключей. `python -m compileall -q src tests` завершён без ошибок.

В текущем Linux-контейнере отсутствуют `PySide6` и `pyqtgraph`, поэтому полный pytest,
Ruff, GUI/offscreen и физическая печать здесь не запускались. Эти проверки обязательны в
штатном Windows-окружении проекта перед публикацией релиза.

## Ручной Windows smoke-test

1. Откройте глубинную форму, нажмите `F4` и убедитесь, что появляется компактная панель
   «Выноска / Комментарий / Изображение / Все…» с понятными подсказками.
2. Создайте объекты из панели и правым щелчком в точной позиции графика. Проверьте привязки
   к глубине, времени, дорожке и кривой.
3. Измените шрифт, размер, начертание, цвета, прозрачность, фон, рамку, линию-выноску,
   стрелку, выравнивание, тень, поворот и геометрию.
4. Перетащите объект и измените размер за маркер. Проверьте Undo/Redo, блокировку,
   дублирование и удаление.
5. Щёлкните по кривой: карточка должна показать мнемонику, точное значение и глубину/время.
   Проверьте «Сохранить для печати» и «Отмена».
6. Повторите сценарий на временной форме и после переключения вертикального индекса.
7. Закройте и повторно откройте проект: текст, изображения, стиль и привязки должны сохраниться.
8. Выполните сращивание LAS, затем Undo/Redo сращивания: аннотации скважины не должны исчезать.
9. Сравните экран, предпросмотр PDF, экспорт PDF и физическую печать. Проверьте также
   `print_enabled=false`, HiDPI 125–200 %, книжную/альбомную ориентацию и переносы текста.

# Проверка версии 0.7.13

1. Откройте планшет, выберите исходную кривую и включите карандаш.
2. Убедитесь, что курсор компактный, а точка изменения совпадает с кончиком грифеля.
3. Проверьте свободный штрих: после отпускания новая линия должна остаться, зависимости — пересчитаться, проект — получить `*`.
4. Нажмите отдельную кнопку «Соединить точки», поставьте минимум две точки и примените их по очереди кнопкой «Соединить», Enter и двойным щелчком.
5. Проверьте кнопки «Отменить»/«Повторить», затем `Ctrl+Z`/`Ctrl+Shift+Z`; исходная и зависимые кривые должны возвращаться синхронно.
6. Нажмите дискету, затем выполните Undo: история должна сохраниться, а проект снова получить признак несохранённых изменений.
7. До нажатия дискеты закройте проект: программа должна предложить сохранить, не сохранять или отменить.
8. Откройте Конструктор при тёмной теме Windows и проверьте навигацию, списки, таблицы, вкладки, сворачиваемые разделы и дочерние редакторы.
9. В галерее первым должен быть шаблон «МАСТЕРЛОГ — эталонная шапка и глубинная форма». Создайте пользовательскую копию и замените обе зоны логотипов.

# Проверка планшетного карандаша 0.7.9

Дата: 21 июля 2026

Проверены постоянная панель карандаша в планшете, выбор видимой исходной кривой,
рисование мышью без перехода на отдельную вкладку, оранжевый preview, линейная,
логарифмическая и кальциметрическая шкалы, возрастающая/убывающая ось, защита
расчётных кривых и интеграция с Undo/Redo.

Результат полного запуска: `1012 passed, 1 skipped`. `ruff check` и `compileall`
завершены без ошибок.

# Проверка среза редактируемых подписей и стратиграфии

Дата: 20 июля 2026

Проверено: заводской и проектный стратиграфический справочник, переопределение/сброс,
сериализация проектных единиц, полный редактор дорожки, сохранение пользовательского названия
при замене кривых, переименование объединённого раздела, рендер и drag-ввод стратиграфии.

Результат полного запуска: `932 passed, 1 skipped`. `ruff check` и `compileall` завершены без
ошибок.

# Тестирование и контроль качества

## Обязательное правило

Каждое исправление и новый инкремент должны сопровождаться:

- тестом основного успешного сценария;
- тестами ошибок и граничных значений для изменённой логики;
- интеграционным тестом, если меняется взаимодействие модулей;
- обновлением README, архитектуры, плана или документа инкремента, если меняется поведение;
- успешным прохождением pytest, Ruff, mypy и проверки чистоты diff.

Исправление дефекта начинается с воспроизводящего теста. Тест должен завершаться ошибкой до
исправления и проходить после него.

## Локальная проверка

```bash
.venv/bin/python scripts/run_tests.py
.venv/bin/ruff check src tests

# Производительность экранного peak sampling на 2 млн отсчётов
PYTHONPATH=src .venv/bin/python benchmarks/benchmark_curve_sampling.py
.venv/bin/mypy src
git diff --check
```

Qt-тесты запускаются с платформой `offscreen` и software-rendering. Скрипт
`scripts/run_tests.py` до импорта pytest отключает посторонние глобальные плагины, которые не
нужны проекту и могут вмешиваться в завершение native Qt runtime. Активная графическая сессия
не требуется. После получения кода pytest скрипт сбрасывает потоки вывода и завершает
процесс напрямую, чтобы известный сбой native Qt при финальном уничтожении глобальных
singletons не подменял уже рассчитанный результат тестов. Сами тесты выполняются полностью.

## Проверка пакета

Инструменты сборки устанавливаются в игнорируемое виртуальное окружение:

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m build --wheel --no-isolation
unzip -t dist/*.whl
unzip -l dist/*.whl | grep -E 'LICENSE|geologist-logo.png|lithotypes.ru.json'
```

`setuptools` и `wheel` объявлены в `[build-system]`, а CLI `build` входит в dev extras.
Каталоги `.venv/`, `build/`, `dist/` и `*.egg-info/` находятся в `.gitignore` и не должны
попадать в коммиты.

## Матрица тестов

| Область | Тип проверки |
|---|---|
| Расчёты и domain-модели | Модульные тесты численных результатов и ограничений |
| Formula Profiles UI | RU/KK/EN passport labels, localized DEXP descriptions, mapping and execution |
| Interval Statistics UI | RU/KK/EN title, interval, count/min/max/mean headers and validation messages |
| Depth Annotations UI | RU/KK/EN title, columns, actions, close button and project-tree label |
| Lithology Intervals UI | RU/KK/EN labels/actions, EN catalog names and stable lithotype IDs |
| Interpretation Intervals | Domain validation, same-type overlap, CRUD, Undo/Redo, project v15, JSON/CSV/Excel and RU/KK/EN UI |
| Description Templates UI | RU/KK/EN title, columns, actions, close button and project-tree label |
| Lithology Legend UI | RU/KK/EN headers/empty state, localized name resolver and stable codes/IDs |
| Lithotype Catalog UI | RU/KK/EN table/form/actions and language-independent system/project state |
| Track Inspector UI | RU/KK/EN summary/settings and stable linear/logarithmic model values |
| Data Inspector UI | RU/KK/EN tabs/tables/messages, curve metadata, indexes and LAS header controls |
| Tablet workflow UI | RU/KK/EN menus/dialogs/messages and stable TrackKind/XScale values |
| LAS Curve Browser | Mnemonic/unit/description search, finite coverage, recommended selection, family separation and main-window integration |
| Sensors catalog | Schema v1 validation, aliases, Cyrillic/Latin homoglyphs, units, external JSON, viewer search and reference ranges |
| Mouse interval editing | Depth snapping, create/resize preview, edge choice, cancellation, controller validation and Undo/Redo integration |
| Graph ranges | Per-track auto/manual X range, data-derived defaults and manual/full depth interval |
| Tablet depth/time navigation | MD/TVD/TVDSS/TIME/DATETIME selection, datetime labels, wheel zoom/scroll, explicit scrollbar, range clamp, go-to, synchronized tracks and layout v8 migration |
| Depth normalization UI | RU/KK/EN directions/confirmation and non-destructive copy workflow |
| Basic Gas Ratio UI | RU/KK/EN command/status/log with stable calculated curve mnemonics |
| Normalized gas | C1 и reference C1–C5/TG profiles, passports, parameters, units, control examples, NaN domain и provenance |
| Custom formulas | Safe AST, versioned provenance, transitive STALE, batch preview/Undo/Redo и RU/KK/EN calculation passport с missing inputs |
| Formula execution passports | DEXP/normalized profiles, actual mapping, curve ID/unit/provenance/state, parameters и output passport |
| User profiles | Stable ID, persistence, selection, update, active-profile deletion and corrupt settings |
| DEXP/NCT | DEXP/DEXPC profiles, explicit NCT calibration, DEXPC−NCT curve and RU/KK/EN dialog |
| LAS и другие входные форматы | Успешный импорт, повреждённый файл, неверный тип |
| CSV/TXT import | Delimiter, encoding, preview, numeric/ISO/DATE+TIME index, timezone, units, NULL и bad rows |
| Excel import | XLS/XLSX/XLSM, LibreOffice, формулы, листы, header, DATE+TIME UI и ошибки |
| Universal import | Маршрутизация LAS/CSV/TXT/Excel и безопасная отмена до выбора файла |
| Localization | Равенство ключей RU/KK/EN, QSettings, выбранный язык оболочки и print terms |
| Диагностика LAS | Отпечаток источника, версия, NULL, направление, дубликаты и заголовок |
| Lossless LAS | Точный byte round-trip, BOM/кодировка, переводы строк, порядок секций |
| Source artifacts | Save As, SHA-256/размер, tamper detection и защита пути |
| Lossless export | Замена известных секций, сохранение custom bytes, BOM/CRLF и конфликты |
| LAS ExportPlan | Версия, WRAP, NULL, точность, предупреждения и блокирующие ошибки |
| LAS Export UI | RU/KK/EN labels, compatibility version, custom sections and dialog buttons |
| Multi-index | Legacy compatibility, active depth/time, detection evidence и project v6 round-trip |
| Time normalization | ISO-8601, DATE+TIME, custom format, IANA/offset/naive, DST, NaT и Unix scale |
| Data Inspector | Summary, indexes, missing curve values, import issues и ручной active index |
| LAS Header Editor | VERSION/WELL/PARAMETER, защищённые поля, координаты, NULL, синхронизация и Undo/Redo |
| LAS Table Editor | RU/KK/EN, ячейки, multi-cell selection, display formats, constant/noise, copy/paste и gas recalc |
| Curve Metadata Editor | Мнемоники, UOM, описания, конфликты с индексами, Undo/Redo и canonical ID |
| Project persistence | Project v8 round-trip, Masterlog templates/anchors, legacy migration, import provenance, schema validation и hash mismatch |
| LAS source profile | Версия, WRAP, NULL, кодировка, fingerprint, artifact status и export defaults |
| LAS import policy | Clean/warning/error для strict, compatible и manual review |
| Проект и миграции | Round-trip, legacy-версии, повреждённые данные |
| Атомарное хранение | Успешная замена и очистка после сбоя |
| Контроллеры | Сценарии через repository/model без Qt |
| Plugin API | Контракт регистрации и несовместимые плагины |
| Qt UI | Headless-интеграционные пользовательские сценарии |
| Branding resources | Загрузка пакетного PNG, масштабирование и иконка приложения |
| LAS Table Editor | Виртуальная модель, read-only индексы/расчёты, per-column display, full-precision edit и пересчёт |

## Принципы

- Тесты не зависят от сети, времени запуска и порядка выполнения.
- Пользовательские файлы не изменяются: используются `tmp_path` и тестовые объекты.
- Для внешних библиотек тестируется наш адаптер, а не внутреннее устройство библиотеки.
- Приватные детали реализации не проверяются, если доступно стабильное наблюдаемое состояние.
- Количество тестов не заменяет проверку рисковых ветвей и бизнес-инвариантов.

## Runtime language and vertical interval regression

The current source archive was validated with `QT_QPA_PLATFORM=offscreen PYTHONPATH=src pytest -q`:

- `855 passed`;
- `1 skipped`;
- preset depth/time interval selection updates all tracks;
- typed interval values apply without Enter;
- the interval survives widget resize;
- runtime `ru → kk → en` switching preserves project and tablet camera state.

## Universal Print Center regression

Проверяются доступность форматов, построение A4 portrait/landscape job, физический printer mode без файлового пути, реальные размеры PNG/JPEG по DPI, нормализация расширений, профильные настройки, callback печати из Form Manager, PDF printer renderer и восстановление экранных ширин планшета. Текущий регрессионный набор: `926 tests collected`; результат последнего полного запуска — `925 passed, 1 skipped` с нормальным кодом завершения. Дополнительно выполняются `python -m ruff check src tests` и `python -m compileall -q src`.

## LAS Editor 2 regression — 21 July 2026

```text
python scripts/run_tests.py
952 passed, 1 skipped in 24.61s
python -m ruff check src tests
All checks passed!
python -m compileall -q src
completed without errors
```

The run covers depth normalization, progressive merge, external LAS insertion, pencil edits,
dependent recalculation, spreadsheet clipboard operations, exports, project persistence, forms,
printing, and RU/KK/EN resources.
