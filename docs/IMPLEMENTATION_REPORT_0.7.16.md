# Итоговый отчёт по реализации 0.7.16

## 1. Краткое описание реализации

В приложение добавлен безопасный импорт GeoScape/Borland Paradox DB с преобразованием в существующую многоиндексную модель `Dataset`. После импорта данные открываются штатным редактором, используются существующими таблицами, графиками, проектом, планшетами и LAS-export. Параллельный LAS-редактор или отдельное хранилище кривых не создавались.

Путь данных:

```text
GeoScape / Paradox DB
        ↓
format detector + bounded reader
        ↓
quality/index analysis + user import plan
        ↓
existing Dataset / DatasetIndex / CurveData
        ↓
existing editor / project / LAS / graphs / tablets
```

## 2. Новые файлы

### Код

- `src/geoworkbench/importers/paradox/__init__.py`
- `src/geoworkbench/importers/paradox/models.py`
- `src/geoworkbench/importers/paradox/bundle.py`
- `src/geoworkbench/importers/paradox/detector.py`
- `src/geoworkbench/importers/paradox/decoder.py`
- `src/geoworkbench/importers/paradox/reader.py`
- `src/geoworkbench/importers/paradox/analysis.py`
- `src/geoworkbench/importers/paradox/importer.py`
- `src/geoworkbench/importers/paradox/profiles.py`
- `src/geoworkbench/importers/paradox/channel_dictionary.py`
- `src/geoworkbench/importers/paradox/batch.py`
- `src/geoworkbench/services/time_to_depth_conversion.py`
- `src/geoworkbench/project/time_to_depth_controller.py`
- `src/geoworkbench/ui/paradox_import_dialog.py`
- `src/geoworkbench/ui/paradox_batch_dialog.py`
- `src/geoworkbench/ui/time_to_depth_dialog.py`
- `src/geoworkbench/resources/geoscape_channels.json`

### Тесты

- `tests/test_paradox_import.py`
- `tests/test_paradox_batch.py`
- `tests/test_time_to_depth_conversion.py`

### Документация и проверка

- `docs/ru/PARADOX_IMPORT.md`
- `docs/kk/PARADOX_IMPORT.md`
- `docs/en/PARADOX_IMPORT.md`
- `docs/ru/RELEASE_NOTES_0.7.16.md`
- `docs/kk/RELEASE_NOTES_0.7.16.md`
- `docs/en/RELEASE_NOTES_0.7.16.md`
- `docs/RELEASE_NOTES_0.7.16.md`
- `VALIDATION_PARADOX_0.7.16.json`
- `docs/IMPLEMENTATION_REPORT_0.7.16.md`

## 3. Изменённые файлы

- `README.md`, `pyproject.toml`, `src/geoworkbench/__init__.py`;
- `src/geoworkbench/ui/main_window.py`;
- `src/geoworkbench/data/las_adapter.py`;
- `src/geoworkbench/data/las_export_plan.py`;
- `src/geoworkbench/resources/i18n/ru.json`;
- `src/geoworkbench/resources/i18n/kk.json`;
- `src/geoworkbench/resources/i18n/en.json`;
- `tests/test_las_export_plan.py`, `tests/test_version.py`;
- `VALIDATION.txt`, `docs/TESTING.md`, `docs/CHANGELOG.md`, `docs/DOCUMENTATION_INDEX.md`;
- корневые и локализованные `PROJECT_STATUS`, `PROJECT_PLAN`, `README`.

## 4. Архитектура

- `detector.py` отличает SQLite, Paradox и неизвестный бинарный файл по содержимому;
- `bundle.py` ищет одноимённые PX/TV/FAM без учёта регистра;
- `reader.py` читает заголовок, схему и блоки только через `rb`, с проверкой границ и безопасных лимитов;
- `decoder.py` декодирует поля и изолирует ошибку отдельного значения;
- `analysis.py` оценивает кандидаты глубины/времени и формирует диагностику качества;
- `importer.py` создаёт обычный `Dataset` с несколькими `DatasetIndex`;
- `profiles.py` применяет профиль только при точном совпадении SHA-256 сигнатуры схемы;
- `batch.py` использует тот же importer и существующий LAS writer;
- UI запускает чтение и создание документа в рабочих потоках, поддерживает прогресс и отмену.

## 5. Поддерживаемые варианты Paradox

На реальных образцах подтверждены Paradox 7.x и типы:

- `NUMBER`;
- `LONG`;
- пустые значения.

Автоматическими модульными тестами дополнительно покрыты декодеры:

- Alpha/String;
- Date;
- Short;
- Currency;
- Logical;
- Time;
- Timestamp;
- AutoIncrement;
- BCD;
- Bytes;
- NULL.

Типы, отсутствовавшие в реальных образцах, считаются ограниченной best-effort поддержкой до проверки на дополнительных исходных таблицах.

## 6. Правила определения глубины

Оценка кандидата учитывает заполненность, монотонность, диапазон, стабильность положительного шага, имя, повторы, обратный ход и сходство с календарным временем. При близких кандидатах классификация становится `mixed`, и пакетная конвертация без профиля запрещается.

- `BLData.db`: основной кандидат `S113`, диапазон 309.2–1717.6 м, номинальный шаг 0.4 м;
- `D250.db`: близкие кандидаты `S101`, `S115`, `S108`; требуется подтверждение пользователя.

## 7. Правила определения времени

Поддерживаются:

- OLE/Delphi Automation days;
- Unix seconds/milliseconds/microseconds/nanoseconds;
- относительные секунды;
- относительные миллисекунды;
- типизированные Paradox Date/Time/Timestamp на уровне декодера.

Для выбранного числового времени создаётся индекс `TIME` в секундах от начала и, при наличии календарной шкалы, индекс `DATETIME`. Исходное число сохраняется отдельной кривой `<source>_RAW`.

## 8. Правила конвертации LAS

- глубинный режим: активный индекс экспортируется первым как `DEPT` с единицей глубины;
- временной режим: активный числовой индекс экспортируется первым как `TIME` с единицей секунд;
- `STRT` и `STOP` берутся из фактического активного индекса;
- `STEP` рассчитывается как медианный положительный шаг;
- NULL задаётся планом импорта/экспорта;
- неизвестные числовые каналы сохраняют исходную мнемонику и пустую единицу;
- исходный DB никогда не становится целью сохранения;
- пакетный режим после записи вызывает существующий LAS-reader для обязательного round-trip, когда `lasio` доступен.

TIME → DEPTH создаёт новый производный набор. Поддерживаются first, last, mean, median, min, max, nearest и явная linear interpolation. Без выбора linear пустые интервалы не заполняются автоматически.

## 9. Известные ограничения

1. В текущем Linux-контейнере отсутствуют `PySide6`, `pyqtgraph` и `lasio`; поэтому полный Qt/offscreen-прогон, физическая печать и фактический `DB → LAS → current LAS-reader` здесь не выполнены.
2. Реальные образцы содержат только `NUMBER` и `LONG`; остальные декодеры проверены синтетически, но требуют дополнительных реальных файлов.
3. Alpha/Bytes читаются и доступны анализатору/предпросмотру, но стандартный LAS 2.0 и текущая модель кривых предназначены для числовых рядов; такие поля не превращаются в числовые LAS-кривые.
4. Автоматическое объединение раздельных Date + Time полей в один календарный индекс пока не выполняется отдельным мастером; полноценный Timestamp/OLE/Unix и ручной выбор числового времени поддерживаются.
5. Профиль можно загрузить и применить с проверкой сигнатуры, но автоматический поиск профиля в пользовательском каталоге пока не включён.
6. Аномалии показываются в таблице качества и могут быть исправлены в существующем редакторе; отдельный пошаговый мастер «оставить/исключить/интерполировать/заменить другим каналом» пока не добавлен.

## 10. Результаты тестов

- `python -m compileall -q src tests` — PASS;
- целевой non-GUI regression suite — `119 passed`;
- RU/KK/EN — по 1445 одинаковых ключей;
- пропуски/лишние ключи — 0;
- расхождения named placeholders — 0;
- Ruff, mypy и package build не запускались: соответствующие инструменты отсутствуют в контейнере.

## 11. Проверка BLData.db

- Paradox 7.x;
- 3488 объявленных и 3488 прочитанных записей;
- 70 полей: 69 `NUMBER`, 1 `LONG`;
- комплект DB/PX/TV/FAM найден автоматически;
- импортировано 70 исходных каналов;
- пропущено каналов: 0;
- пропущено записей: 0;
- пустых каналов: 43;
- предупреждений уровня Warning: 6;
- критических ошибок: 0;
- `S113` подтверждён как основной кандидат глубины;
- `S0` распознан как OLE/Delphi время;
- исходное время сохранено как `S0_RAW`.

## 12. Проверка D250.db

- Paradox 7.x;
- 1739 объявленных и 1739 прочитанных записей;
- 101 поле `NUMBER`;
- импортирован 101 исходный канал;
- пропущено каналов: 0;
- пропущено записей: 0;
- пустых каналов: 26;
- предупреждений уровня Warning: 0;
- критических ошибок: 0;
- `S0` распознан как OLE/Delphi время;
- глубина неоднозначна: `S101`, `S115`, `S108` имеют близкую оценку;
- автоматическая пакетная конвертация без профиля блокируется.

## 13. Инструкция пользователю

1. Откройте **Файл → Импортировать GeoScape / Paradox DB** или перетащите `.db` в окно.
2. Проверьте найденные PX/TV/FAM и сведения о таблице.
3. Подтвердите тип набора, канал глубины и/или времени.
4. Проверьте первые и последние 20 строк.
5. Настройте импорт каналов, мнемоники, единицы, NULL и правило повторяющейся глубины.
6. Нажмите **Открыть в редакторе** или **Сохранить LAS**.
7. Для повторяющихся структур сохраните профиль.
8. Для нескольких файлов используйте **Инструменты → Пакетная конвертация DB → LAS**.
9. Для временного набора с глубиной используйте **Преобразовать временные данные в глубинные**.
10. Сохраните проект или новый LAS; исходный DB остаётся только для чтения.

## 14. CHANGELOG 0.7.16

Добавлены безопасный Paradox detector/reader, комплект DB/PX/TV/FAM, единая Dataset-интеграция, анализ глубины/времени, профили и словарь, контроль качества, глубинный и временной LAS, TIME → DEPTH, пакетный конвертер, прогресс/отмена, RU/KK/EN и тесты на реальных образцах.

## 15. Итоговый архив

`GEOLOG_GASRATIO_Pixler-v0.7.16-geoscape-paradox-importer.zip`

## Контроль сохранности

- Исходные DB/PX/TV/FAM не изменены: SHA-256 до и после совпадает.
- Количество импортированных записей: BLData — 3488; D250 — 1739.
- Количество импортированных каналов: BLData — 70; D250 — 101.
- Количество пропущенных записей: 0 и 0.
- Количество предупреждений Warning: 6 и 0.
- Фактическое повторное открытие созданного LAS в этом контейнере не выполнено из-за отсутствия `lasio`; код обязательной проверки встроен в пакетный сервис и должен быть подтверждён в штатной Windows-среде.
