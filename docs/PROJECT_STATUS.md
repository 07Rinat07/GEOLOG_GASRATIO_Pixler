# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.33, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline 0.7.28: Ruff чист, mypy — 0 ошибок
в 262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено. Для 0.7.33 выполнены
`compileall` и доступная headless/regression/source-integrity регрессия: 731 тест пройден,
4 платформенных сценария пропущено. Три LAS-roundtrip теста требуют `lasio`, один Qt-сценарий
требует `PySide6`; полный сбор также недоступен без PySide6, pyqtgraph и lasio. Ruff и mypy в
контейнере отсутствуют. Сборка остаётся тестовой до повторного полного gate и обязательной
Windows/HiDPI/PDF/physical-print матрицы.

## Подтверждённая рабочая основа

- безопасные LAS 1.2/2.0, CSV/TXT, Excel и GeoScape/Paradox workflows;
- multi-dataset/multi-index проект формата v16;
- Semantic Channel Dictionary и явный UOM quantity-class dictionary;
- сериализуемый semantic binding каждой кривой;
- единый интерактивный Import Review для CSV/Excel/LAS/Paradox;
- выбор и проверка индекса, ручные semantic/UOM overrides, дополнительный NULL-sentinel;
- QC по NULL, duplicate, gap, order, unresolved, UOM conflict, all-null и duplicate kind;
- атомарное подтверждение через deep-copy controller и project-session port;
- многотрековый планшет, формы, Masterlog, PDF, Print Center, аннотации и project assets;
- синхронные пользовательские документы RU/KK/EN.

## Результаты текущего среза

| Проверка | Результат |
|---|---|
| Import Review controller | initial plan, preview и commit работают без мутации исходного dataset |
| Импортные jobs | CSV, Excel, LAS и Paradox вызывают review до регистрации в проекте |
| Отмена | dataset/well не создаётся, `dirty` не меняется |
| QC | блокирующие ошибки отключают commit; предупреждения остаются видимыми |
| Локализация | каталоги RU/KK/EN содержат одинаковые 1733 ключа |
| Доступная регрессия | 731 passed, 4 skipped |
| Project format | остаётся v16 |

## Технический долг с наибольшим риском

- `tablet/tablet_view.py` и `ui/main_window.py` остаются крупными orchestration-классами;
- полный Ruff/mypy/Qt/LAS gate 0.7.33 нужно повторить в полном окружении;
- интерактивный диалог нужно проверить вручную на Windows при больших таблицах и HiDPI;
- отсутствуют golden fixtures общей экранной и печатной геометрии;
- изменение UOM в Import Review исправляет метаданные, но не выполняет пересчёт значений.

## Следующая контрольная точка

Следующий вертикальный срез — Report Passport: fingerprint источника, semantic bindings,
версии формул, UOM, revision формы, язык и настройки рендера. После него — golden fixtures.
Ручной Windows GUI/HiDPI/PDF/physical-print smoke-test остаётся обязательным условием stable.

Подробности: [Import Review](IMPORT_REVIEW.md),
[Semantic Channel Dictionary](SEMANTIC_CHANNEL_DICTIONARY.md),
[план](PROJECT_PLAN.md) и [проверки](TESTING.md).
