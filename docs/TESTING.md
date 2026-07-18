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
.venv/bin/pytest -q
.venv/bin/ruff check src tests

# Производительность экранного peak sampling на 2 млн отсчётов
PYTHONPATH=src .venv/bin/python benchmarks/benchmark_curve_sampling.py
.venv/bin/mypy src
git diff --check
```

Qt-тесты запускаются с платформой `offscreen`, настроенной в `tests/conftest.py`, и не
требуют активной графической сессии.

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
| Description Templates UI | RU/KK/EN title, columns, actions, close button and project-tree label |
| Lithology Legend UI | RU/KK/EN headers/empty state, localized name resolver and stable codes/IDs |
| Lithotype Catalog UI | RU/KK/EN table/form/actions and language-independent system/project state |
| Track Inspector UI | RU/KK/EN summary/settings and stable linear/logarithmic model values |
| Data Inspector UI | RU/KK/EN tabs/tables/messages, curve metadata, indexes and LAS header controls |
| Tablet workflow UI | RU/KK/EN menus/dialogs/messages and stable TrackKind/XScale values |
| Graph ranges | Per-track auto/manual X range, data-derived defaults and manual/full depth interval |
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
