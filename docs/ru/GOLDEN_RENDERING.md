# Детерминированные golden fixtures рендера

## Назначение

Golden fixtures фиксируют общий контракт экранного планшета и печатного Masterlog до
ручной проверки конкретного Qt/Windows-устройства. Они обнаруживают незаявленные изменения
геометрии, порядка легенды, lithotype pattern и размещения аннотаций.

Эталон не содержит дату создания, абсолютные пути, случайные ID или версию приложения.
Одинаковый исходный контракт всегда формирует байт-в-байт одинаковые JSON и SVG.

## Состав

Эталоны находятся в `tests/golden_rendering`:

- `grid_screen_print_v1.json` — major/minor divisions, normalized fractions, экранные
  координаты в px и печатные координаты в mm;
- `legend_multilingual_v1.json` — порядок, deduplication, unknown fallback и подписи
  RU/KK/EN;
- `lithotype_patterns_v1.json` — compact/legacy aliases, factory asset SHA-256, размеры
  bitmap tile и физический размер при 96 DPI;
- `annotations_screen_print_v1.json` — box, anchor, leader endpoint, rotation и clipping
  для экрана и печати;
- `screen_tablet_v1.svg` и `print_masterlog_v1.svg` — визуальные составные эталоны.

Каждый JSON использует schema `geoworkbench.render-golden/v1` и содержит SHA-256
канонического payload.

## Общие границы реализации

- `tablet/grid_geometry.py` является Qt-независимым источником major/minor geometry;
- экранный `grid_renderer` и печатный Masterlog используют один division contract;
- `build_lithology_legend_from_ids()` одинаково разрешает code/name/color/pattern и
  неизвестные литотипы для экрана и печати;
- `lithology_pattern_catalog.py` разрешает legacy alias в конкретный factory bitmap и
  проверяет его content SHA-256 без Qt;
- `annotation_layout.py` переводит reference pixels в экранные px или печатные mm и
  одинаково вычисляет box и leader endpoint, включая rotation.

## Обновление эталона

Из корня проекта:

```powershell
.\.venv\Scripts\python.exe tools\update_render_goldens.py
```

Команда также работает через активный интерпретатор: `python tools/update_render_goldens.py`.

Обновление golden допустимо только вместе с объяснением ожидаемого изменения рендера.
Тест `test_committed_render_goldens_match_deterministic_generator` сравнивает все файлы
байт-в-байт, поэтому случайное изменение сразу блокирует gate.

## Проверки

Автоматический gate проверяет:

- совпадение committed и regenerated fixtures;
- SHA-256 каждого JSON payload;
- одинаковые normalized grid fractions для px/mm;
- сохранение physical tile size bitmap-литотипов;
- порядок и локализацию legend;
- масштабирование annotation geometry из 96-DPI reference pixels в mm;
- отсутствие machine-specific path и timestamp.

Qt raster/PDF comparison с платформенным tolerance, HiDPI 100–200% и физическая печать
остаются отдельной обязательной Windows-матрицей перед stable.
