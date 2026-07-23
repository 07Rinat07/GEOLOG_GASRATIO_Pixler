# Статус проекта

Срез: 23 июля 2026 года. Версия пакета: 0.7.35, тестовая сборка.

## Решение о выпуске

Последний полностью подтверждённый baseline 0.7.28: Ruff чист, mypy — 0 ошибок в 262
исходных файлах, полный pytest — 1217 пройдено и 10 пропущено. Для 0.7.35 выполнены
`compileall` и доступная headless/regression/source-integrity регрессия: 734 теста пройдено,
4 платформенных сценария пропущено. Три LAS-roundtrip сценария исключены из доступного
запуска без `lasio`; Qt/pyqtgraph-зависимые файлы не собираются без `PySide6` и `pyqtgraph`.
Ruff и mypy в контейнере отсутствуют. Сборка остаётся
тестовой до полного gate и Windows/HiDPI/PDF/physical-print матрицы.

## Подтверждённая основа

- безопасный импорт LAS, CSV/TXT, Excel и GeoScape/Paradox;
- проект формата v16 с Semantic Channel Dictionary и Import Review;
- детерминированный Report Passport schema v1;
- JSON/SVG golden fixtures для grid, legend, lithotypes и annotations;
- общая screen/print geometry для сетки, легенды, pattern identity и annotation layout;
- синхронная документация RU/KK/EN.

## Результаты 0.7.35

| Проверка | Результат |
|---|---|
| Golden schema | `geoworkbench.render-golden/v1`, canonical JSON и SHA-256 |
| Grid | одинаковые normalized fractions в screen px и print mm |
| Legend | общий порядок, deduplication, unknown fallback и RU/KK/EN |
| Lithotypes | factory bitmap SHA-256 и physical tile size при 96 DPI |
| Annotations | общий box/leader/rotation/clipping contract |
| Visual | screen и print SVG воспроизводятся байт-в-байт |
| Целевые golden-contract тесты | 19 passed |
| Доступная регрессия | 734 passed, 4 skipped, 3 LAS scenarios deselected; Qt modules unavailable |
| Формат проекта | v16 |

## Оставшийся риск

- повторить полный Ruff/mypy/Qt/LAS gate;
- выполнить Windows/HiDPI/PDF/physical-print smoke-test;
- structural/SVG goldens не заменяют platform raster comparison с tolerance;
- унифицировать `ReportDefinition`, interval selection и output fingerprint.

## Следующая контрольная точка

Единая `ReportDefinition` и один interval selection для preview, PDF и табличного экспорта.

См. [Golden rendering](GOLDEN_RENDERING.md), [Report Passport](REPORT_PASSPORT.md) и
[общий план](../PROJECT_PLAN.md).
