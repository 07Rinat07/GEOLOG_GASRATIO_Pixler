# Архитектура Universal Constructor 0.7.0

Дата: 21 июля 2026

## Принцип интеграции

Universal Constructor не создаёт параллельный формат документов. Он объединяет уже
существующие подсистемы проекта:

- `FormManagerDialog` — экранные формы планшета;
- `MasterlogTemplateController` — печатные шаблоны, шапка, колонки и параметры страницы;
- `MasterlogHeaderDialog` — WYSIWYG-редактор шапки;
- `MasterlogSymbolsDialog` — глубинные обозначения;
- `masterlog_renderer.py` — preview, PDF и физический печатный вывод;
- `masterlog_preflight.py` — проверка шаблона перед выводом.

Единая точка входа находится в `UniversalConstructorDialog`.

## Главное меню

`MainWindow._create_actions()` создаёт меню `menu.constructor`. Действие
`constructor.open` имеет сочетание `Ctrl+Shift+K` и вызывает `MainWindow.show_constructor()`.
Диалог получает текущий `MasterlogTemplateController`, поэтому работает с активной сессией,
скважиной, dataset, изображениями, литотипами и шаблонами без копирования состояния.

## Каталог ресурсов

### ConstructorAssetRegistry

`src/geoworkbench/form_constructor/asset_registry.py` загружает два manifest-файла:

- `resources/constructor_assets/lithology/manifest.json`;
- `resources/constructor_assets/symbols/manifest.json`.

Реестр проверяет schema, уникальность ID, размеры, существование файлов и SHA-256. Поиск
работает по ID, категории, RU/KK/EN-названию и псевдонимам.

### Установка в проект

`asset_install.py` преобразует поддерживаемый Qt raster в детерминированный PNG `ImageAsset`.
Операция идемпотентна: существующий asset с тем же SHA-256 повторно не записывается. Для
литотипа дополнительно создаётся `ProjectLithotype` с `pattern_key=constructor:<asset_id>`.

`tablet/lithology_patterns.py` распознаёт такой pattern key и создаёт tiled `QBrush` из
упакованного BMP. Исходная текстура не растягивается и не сглаживается.

## Стабилизация Form Manager

`FormManagerDialog` не перестраивает тяжёлый preview прямо внутри сигнала выбора.

1. Выбор увеличивает revision в `PreviewRevisionGate`.
2. Одноразовый `QTimer` с задержкой 90 мс откладывает построение.
3. Перед применением результата проверяется, что revision и выбранная форма не устарели.

Это предотвращает применение старого preview после быстрого выбора другой формы.

## Глубинная навигация планшета

`TabletView` устанавливает event filter не только на pyqtgraph-графики, но и на viewport,
контейнеры дорожек и шапки.

- обычное колесо и pixel delta touchpad изменяют положение по глубине;
- `Ctrl + колесо` изменяет видимый интервал вокруг глубины под курсором;
- одна функция `_handle_depth_wheel()` используется для всех областей.

## WYSIWYG-шапка

Координаты `MasterlogHeaderElement` хранятся в миллиметрах. Холст показывает:

- физическую ширину выбранного A0–A4/Letter/Legal/custom/roll профиля;
- книжную или альбомную ориентацию;
- красную overflow-область за правой границей страницы;
- сетку и привязку;
- итоговые литотипные swatch, изображения и текстовые поля.

Изображения проекта нормализуются в PNG либо сохраняются как проверенный SVG. Renderer и
preview применяют одинаковые свойства `mode`, `rotation` и `opacity`.

## Глубинные обозначения

`CanvasObject` с `object_type=masterlog_symbol` хранит:

- семантическую привязку `depth`, `interval`, `parameter` или `time`;
- `top_depth` и `bottom_depth`;
- `track_id` и `parameter_mnemonic`;
- asset, размер и подпись;
- `x` как ручное смещение X в миллиметрах;
- `properties.offset_y_mm` как ручное смещение Y.

Renderer сначала вычисляет позицию из глубины/параметра, а затем применяет ручное смещение.
Изменение страницы или масштаба не уничтожает исходную привязку.

## Динамическая литологическая легенда

Свойство `scope` поддерживает:

- `used` — реально использованные породы текущего диапазона;
- `all` — весь проектный каталог;
- `manual` — только `selected_lithotype_ids`;
- `used_manual` — использованные плюс выбранные вручную.

Одинаковая логика используется в WYSIWYG-preview и печатном renderer.

## Форматы страниц

`PrintPageFormat` поддерживает A0, A1, A2, A3, A4, Letter, Legal, custom и roll. Форматы
подключены к общему `PrintPageDialog`, Masterlog page dialog, template controller и renderer.

## Preflight

Проверка выявляет:

- отсутствие dataset или колонок;
- выход шапки за страницу/высоту;
- отсутствующие image assets и ручные литотипы;
- слишком мелкий текст;
- недостаточное raster-разрешение относительно 300 DPI;
- отсутствующую колонку обозначения;
- неверный интервал, время, параметр или смещение обозначения;
- отсутствующие curve bindings и некорректный logarithmic range;
- невозможность разбиения на страницы.

## Сохранение

Шаблоны, header elements, columns, `CanvasObject`, `ProjectLithotype` и `ImageAsset` используют
существующую сериализацию проекта. Нового отдельного файла конструктора нет, поэтому
сохранение выполняется стандартными `Ctrl+S` и «Сохранить как».

## Следующие архитектурные задачи

- explicit `screen_form_id ↔ print_template_id` profile;
- команды Undo/Redo для всего WYSIWYG-холста;
- линейки, направляющие, группы и блокировка слоёв;
- drag глубинного обозначения непосредственно на preview;
- переход из preflight issue к объекту редактора;
- Windows E2E smoke-test и физическая печать.

## Device-space lithotype tiling (0.7.2)

`DeviceTiledRectItem` separates interval geometry from brush coordinates. The rectangle remains
in the pyqtgraph depth coordinate system, while the inverse painter world transform is applied to
the texture brush. This prevents the 10–42 px legacy BMP tiles from being stretched by the
non-uniform track/depth transform.

`masterlog_lithology_brush()` applies the same separation to WYSIWYG preview, image rendering,
PDF, and physical printing. It cancels the active millimetre-to-device world transform for the
bitmap and reapplies a 96-DPI reference scale. Consequently, a 14 px source tile remains about
3.7 mm wide instead of becoming a 14 mm block, and its physical density is stable across preview,
300-DPI PDF, and printer devices. Interval geometry, clipping, and borders remain millimetre-based.
