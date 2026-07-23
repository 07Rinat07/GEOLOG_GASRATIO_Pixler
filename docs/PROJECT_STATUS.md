# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.35, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый автоматический baseline 0.7.28: Ruff чист, mypy — 0 ошибок
в 262 исходных файлах, полный pytest — 1217 пройдено и 10 пропущено. Для 0.7.35 выполнены
`compileall` и доступная headless/regression/source-integrity регрессия: 734 теста пройдено,
4 платформенных сценария пропущено. Три LAS-roundtrip сценария исключены из доступного
запуска из-за отсутствующего `lasio`; Qt/pyqtgraph-зависимые файлы в этом контейнере не
собираются без `PySide6` и `pyqtgraph`. Ruff и mypy не установлены. Сборка остаётся тестовой до повторного полного gate и
обязательной Windows/HiDPI/PDF/physical-print матрицы.

## Подтверждённая рабочая основа

- безопасные LAS 1.2/2.0, CSV/TXT, Excel и GeoScape/Paradox workflows;
- multi-dataset/multi-index проект формата v16;
- Semantic Channel Dictionary, UOM quantity classes и сериализуемые semantic bindings;
- интерактивный Import Review с ручными overrides, QC и атомарным commit;
- детерминированный Report Passport schema v1 с SHA-256 проверкой;
- детерминированные JSON/SVG golden fixtures для grid, legend, lithotypes и annotations;
- многотрековый планшет, формы, Masterlog, Print Center и интерпретационные отчёты;
- синхронные пользовательские документы RU/KK/EN.

## Результаты текущего среза

| Проверка | Результат |
|---|---|
| Golden schema | `geoworkbench.render-golden/v1`, canonical JSON и payload SHA-256 |
| Grid | одна normalized major/minor geometry для screen px и print mm |
| Legend | общий resolver порядка, deduplication, unknown fallback и RU/KK/EN подписей |
| Lithotypes | legacy alias закреплён за точным factory bitmap SHA-256 и physical tile size |
| Annotations | общий box/leader contract в reference pixels, px и mm, включая rotation |
| Visual fixtures | `screen_tablet_v1.svg` и `print_masterlog_v1.svg` воспроизводятся байт-в-байт |
| Generator | `tools/update_render_goldens.py` обновляет только `tests/golden_rendering` |
| Целевые golden-contract тесты | 19 passed |
| Доступная регрессия | 734 passed, 4 skipped, 3 LAS scenarios deselected; Qt modules unavailable |
| Project format | остаётся v16 |

## Технический долг с наибольшим риском

- полный Ruff/mypy/Qt/LAS gate 0.7.35 нужно повторить в полном окружении;
- Windows/HiDPI/PDF/physical-print smoke-test остаётся обязательным;
- SVG/structural goldens не заменяют платформенное raster/PDF сравнение с tolerance;
- output и Report Passport sidecar записываются атомарно по отдельности, но не одной
  filesystem-транзакцией;
- output-file fingerprint будет добавлен после унификации `ReportDefinition`.

## Следующая контрольная точка

Следующий вертикальный срез — единая `ReportDefinition` и один interval selection для preview,
PDF и табличного экспорта. Ручной Windows GUI/HiDPI/PDF/physical-print smoke-test остаётся
обязательным условием stable.

Подробности: [Golden rendering](GOLDEN_RENDERING.md), [Report Passport](REPORT_PASSPORT.md),
[Import Review](IMPORT_REVIEW.md), [план](PROJECT_PLAN.md) и [проверки](TESTING.md).
