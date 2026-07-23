# Примечания к выпуску 0.7.35 — Golden Rendering Fixtures

Дата: 23 июля 2026 года. Статус: тестовая сборка.

## Новое

- добавлены четыре детерминированных JSON golden fixture для grid, legend, lithotype patterns
  и annotations;
- добавлены составные SVG-эталоны экранного планшета и печатного Masterlog;
- каждый JSON использует `geoworkbench.render-golden/v1` и SHA-256 canonical payload;
- `tools/update_render_goldens.py` воспроизводит committed fixtures байт-в-байт.

## Общая геометрия

- major/minor grid geometry вынесена в Qt-независимый `tablet/grid_geometry.py`;
- экран и печать используют одинаковые normalized fractions;
- screen и Masterlog legend используют общий `build_lithology_legend_from_ids()`;
- legacy lithotype pattern aliases разрешаются headless-каталогом до конкретного factory
  bitmap с content SHA-256;
- annotation box и leader endpoint вычисляются общим `annotation_layout.py` в px или mm;
- печатные аннотации теперь учитывают rotation при выборе leader endpoint.

## Проверки

- 734 доступных headless/regression/source-integrity теста пройдено;
- 4 платформенных сценария пропущено;
- 3 LAS-roundtrip сценария исключены из запуска без `lasio`; Qt/pyqtgraph-модули недоступны без `PySide6` и `pyqtgraph`;
- 19 целевых golden-contract тестов пройдено;
- `compileall` выполнен без ошибок;
- полный Ruff/mypy/Qt/LAS gate и Windows/HiDPI/PDF/physical-print smoke-test требуется
  повторить в полном окружении.

Формат проекта остаётся v16.
