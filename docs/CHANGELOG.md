## Unreleased — full-height tablet tracks and column context menu

- The depth scale is now a compact dedicated ruler: the redundant rotated label was removed, tick labels use the available width, and resizing the depth column updates the ruler immediately.
- Pinned and scrollable tracks stretch to the complete tablet viewport instead of ending above a blank lower area.
- Right-click works over the header and the complete body of every column.
- Graphical-column context menus now provide direct actions to add curves, choose/replace parameters and curves, and open track properties.
- The curve selection dialog shows mnemonic, unit and description and restores the current track selection when replacing curves.

## Unreleased — depth navigation and compact side panels

- Long depth/time datasets now open in a readable initial viewport instead of being compressed into the full screen height.
- The mouse wheel pans the synchronized vertical window immediately; `Ctrl+wheel` keeps zooming around the pointer.
- Wheel navigation is accepted over the curve area, depth track, track header and plot widget.
- Repeated mapped depth/time samples are averaged for rendering to remove misleading horizontal strokes without changing source LAS data.
- The LAS curve browser and right inspector are collapsed by default and are opened from narrow icon rails with tooltips and shortcuts.
- Only one panel per side is kept open, preserving the maximum tablet workspace.

- Добавлен редактор содержимого дорожки формы: CRUD и порядок `ParameterBinding`, выбор канонического параметра или кривой текущего LAS, цвет, толщина, стиль, шкала и диапазон.
- Редактор формы теперь получает текущий dataset из главного окна; привязки сохраняются в JSON и повторно применяются к планшету.

## Tablet Engine 2.0 — Overlay Engine

- Добавлен `OverlayLayerManager` с независимыми слоями cursor, selection, marker, annotation, preview, tooltip и rubber-band.
- Добавлены управляемые Z-порядок, видимость, dirty-состояние и ревизии каждого слоя.
- Визир, выделение и preview интервалов больше не требуют перестроения кривых.
- Добавлены отдельные API для tooltip и rubber-band.
- Добавлена статистика регистраций, удалений и обновлений overlay-элементов.
# Changelog

## Unreleased — Tablet Engine 2.0 navigation foundation

### Added

- a shared `TabletCamera` model for depth and time navigation;
- cursor-anchored `Ctrl+wheel` zoom;
- keyboard navigation with Home/End/PageUp/PageDown/Up/Down;
- middle-button and `Space + left mouse button` viewport panning;
- focused camera unit tests and GUI navigation regression tests.

### Changed

- wheel scrolling and zoom now use one bounded camera range instead of independent ad-hoc track operations;
- project roadmap, plan, status, architecture, and RU/KK/EN user documentation were synchronized with the approved plan through version 1.0.

## Unreleased — Tablet depth/time navigation

### Русский

- добавлен выбор вертикального индекса MD/TVD/TVDSS/TIME/DATETIME;
- добавлена явная вертикальная полоса прокрутки, кнопки масштаба, полный диапазон и переход к значению;
- колесо прокручивает, `Ctrl+колесо` масштабирует, перетаскивание панорамирует все дорожки синхронно;
- глубинные объекты отображаются во временной шкале через связь TIME↔DEPTH;
- компоновка планшета v8 сохраняет выбранный индекс и мигрирует старые версии;
- regression suite: 750 passed, 1 skipped; Ruff и MyPy без ошибок.

### Қазақша

- MD/TVD/TVDSS/TIME/DATETIME тік индексін таңдау қосылды;
- тік айналдыру жолағы, масштаб батырмалары, толық ауқым және мәнге өту қосылды;
- дөңгелек айналдырады, `Ctrl+дөңгелек` масштабтайды, сүйреу барлық жолақты синхронды жылжытады;
- тереңдік объектілері TIME↔DEPTH байланысы арқылы уақыт шкаласында көрсетіледі;
- планшет компоновкасының v8 нұсқасы таңдалған индексті сақтайды және ескі нұсқаларды көшіреді;
- regression suite: 750 passed, 1 skipped; Ruff және MyPy қатесіз.

### English

- added MD/TVD/TVDSS/TIME/DATETIME vertical-index selection;
- added an explicit vertical scrollbar, zoom buttons, full range, and go-to control;
- the wheel scrolls, `Ctrl+wheel` zooms, and dragging pans every track synchronously;
- depth-anchored objects are displayed on the time axis through TIME↔DEPTH row mapping;
- tablet layout v8 persists the selected index and migrates older layouts;
- regression suite: 750 passed, 1 skipped; Ruff and MyPy pass cleanly.

## Unreleased — Sensors catalog and direct interval editing

### Русский

- нормализованы справочники `Editor/Sensors.DB` и `Geolog-055/Sensors.DB`; добавлены проверенные LAS-псевдонимы;
- добавлены канонические мнемоники, единицы, категории, совместимые семейства дорожек, рекомендуемые диапазоны и происхождение записей;
- добавлен просмотрщик справочника, поиск и подключение внешнего JSON схемы v1;
- панель LAS-кривых показывает каноническую мнемонику и справочный диапазон;
- добавлены режимы выбора, рисования и изменения границ интервалов на планшете;
- мышиные операции используют привязку к LAS, preview, `Esc`, валидацию и Undo/Redo;
- regression suite: 743 passed, 1 skipped; Ruff и MyPy без ошибок.

### Қазақша

- `Editor/Sensors.DB` және `Geolog-055/Sensors.DB` қалыптандырылып, тексерілген LAS бүркеншік аттары қосылды;
- канондық мнемоника, өлшем бірлігі, санат, жолақ тобы, ұсынылатын диапазон және дереккөз қосылды;
- анықтамалықты қарау, іздеу және v1 сыртқы JSON қосу іске асырылды;
- LAS қисықтары панелі канондық мнемоника мен анықтамалық диапазонды көрсетеді;
- планшетте аралықтарды таңдау, сызу және шекарасын өзгерту режимдері қосылды;
- әрекеттер LAS өлшеміне байлау, preview, `Esc`, тексеру және Undo/Redo қолданады;
- regression suite: 743 passed, 1 skipped; Ruff және MyPy қатесіз.

### English

- normalized `Editor/Sensors.DB` and `Geolog-055/Sensors.DB` and added validated LAS aliases;
- added canonical mnemonics, units, categories, compatible track families, reference ranges, and provenance;
- added a searchable catalog viewer and schema-v1 external JSON connection;
- the LAS curve panel now displays canonical mnemonics and reference ranges;
- added select, draw, and boundary-edit modes for interpretation intervals on the tablet;
- mouse operations use LAS snapping, live preview, `Esc`, validation, and Undo/Redo;
- regression suite: 743 passed, 1 skipped; Ruff and MyPy pass cleanly.

## Unreleased — LAS curve browser and readable tablet UX

### Русский

- добавлена закрепляемая панель выбора LAS-кривых с поиском, единицами, описанием, заполненностью и диапазоном;
- добавлена классификация мнемоник по группам Газ/Бурение/Раствор/ГИС/DEXP-NCT/Другое;
- добавлено построение планшета из выбранных кривых, добавление дорожки и замена состава выбранной дорожки;
- базовая компоновка использует рекомендуемый рабочий набор и разделяет физически несовместимые семейства параметров по независимым шкалам;
- планшет переведён на светлый контрастный фон, добавлен устойчивый автоматический X-диапазон и явное состояние «нет числовых данных»;
- пустой журнал скрыт по умолчанию и открывается при ошибках;
- regression suite: 730 passed, 1 skipped; Ruff и MyPy без ошибок.

### Қазақша

- іздеу, өлшем бірлігі, сипаттама, толу пайызы және ауқымы бар LAS қисықтарын таңдау панелі қосылды;
- мнемоникаларды Газ/Бұрғылау/Ерітінді/ГИС/DEXP-NCT/Басқа топтарына жіктеу қосылды;
- таңдалған қисықтардан планшет құру, жолақ қосу және таңдалған жолақ құрамын ауыстыру қосылды;
- базалық компоновка ұсынылған жұмыс жиынын қолданып, физикалық тұрғыдан үйлеспейтін параметр отбасыларын жеке шкалаларға бөледі;
- планшет ашық контрастты фонға ауыстырылды, тұрақты автоматты X ауқымы және «сандық деректер жоқ» күйі қосылды;
- бос журнал әдепкіде жасырылып, қате кезінде ашылады;
- regression suite: 730 passed, 1 skipped; Ruff және MyPy қатесіз.

### English

- added a dockable LAS curve browser with search, units, descriptions, coverage, and actual ranges;
- added mnemonic classification into Gas/Drilling/Mud/Petrophysics/DEXP-NCT/Other groups;
- added tablet creation from selected curves, new-track creation, and selected-track curve replacement;
- the default layout uses a recommended working set and separates physically incompatible parameter families onto independent scales;
- switched tablet plots to a light high-contrast surface, added robust automatic X ranges, and an explicit no-numeric-data state;
- the empty log dock is hidden by default and opens for errors;
- regression suite: 730 passed, 1 skipped; Ruff and MyPy pass cleanly.

## Unreleased — Interpretation tablet visualization

### Русский

- добавлена отдельная планшетная дорожка активной интерпретации с независимыми полосами типов;
- добавлен hit-testing интервалов по полосе и глубине;
- добавлено двустороннее выделение между планшетом, менеджером, деревом проекта и панелью свойств;
- панель свойств позволяет изменять кровлю, подошву, тип, подпись, цвет и комментарий через валидируемый controller/Undo history;
- активные интервалы включены в сводку визирной линии;
- добавлена нормализация выбора при переключении скважин и RU/KK/EN локализация;
- regression suite: 721 passed, 1 skipped; Ruff и MyPy без ошибок.

### Қазақша

- белсенді интерпретация үшін түрлер бойынша тәуелсіз жолақтары бар жеке планшет трегі қосылды;
- жолақ пен тереңдік бойынша аралық hit-testing қосылды;
- планшет, менеджер, жоба ағашы және қасиеттер панелі арасында екіжақты таңдау қосылды;
- қасиеттер панелі төбе, табан, түр, белгі, түс және түсініктемені тексерілетін controller/Undo history арқылы өзгертеді;
- белсенді аралықтар визир сызығының жиынтығына қосылды;
- ұңғымаларды ауыстырғанда таңдауды қалыпқа келтіру және RU/KK/EN локализациясы қосылды;
- regression suite: 721 passed, 1 skipped; Ruff және MyPy қатесіз.

### English

- added a dedicated tablet track for the active interpretation with independent type lanes;
- added interval hit testing by lane and depth;
- added bidirectional selection across the tablet, manager, project tree, and property panel;
- the property panel edits top, bottom, type, label, color, and comment through the validated controller/Undo history;
- active interpretation intervals are included in the cursor summary;
- added selection normalization when switching wells and RU/KK/EN localization;
- regression suite: 721 passed, 1 skipped; Ruff and MyPy pass cleanly.

## Unreleased — Interpretation interval manager

### Русский

- добавлена структура `Project → Well → Interpretation → Intervals`;
- добавлены CRUD, цвета, типы, подписи и комментарии;
- добавлены Undo/Redo и проверка пересечений одного типа;
- формат проекта обновлён до v15 с миграцией v14 → v15;
- добавлены JSON/CSV/Excel экспорт и RU/KK/EN интерфейс;
- regression suite: 714 passed, 1 skipped.

### Қазақша

- `Project → Well → Interpretation → Intervals` құрылымы қосылды;
- CRUD, түстер, түрлер, белгілер және түсініктемелер қосылды;
- Undo/Redo және бір түрдегі аралықтардың қиылысуын тексеру қосылды;
- жоба форматы v15-ке жаңартылып, v14 → v15 көшіруі қосылды;
- JSON/CSV/Excel экспорты және RU/KK/EN интерфейсі қосылды;
- regression suite: 714 passed, 1 skipped.

### English

- added the `Project → Well → Interpretation → Intervals` hierarchy;
- added CRUD, colors, types, labels, and comments;
- added Undo/Redo and same-type overlap validation;
- updated the project format to v15 with v14 → v15 migration;
- added JSON/CSV/Excel export and RU/KK/EN UI;
- regression suite: 714 passed, 1 skipped.

### Обучаемый словарь мнемоник / Үйретілетін сөздік / Trainable mnemonic dictionary

- добавлены пользовательские правила соответствия чужих и канонических мнемоник;
- правила сохраняются между запусками и имеют приоритет над Sensors;
- добавлены создание, редактирование, удаление, импорт и экспорт JSON;
- автоматическая классификация и построение дорожек используют сохранённые правила для следующих LAS-файлов.

### Tablet Engine 2.0 — horizontal viewport, mini-map and LOD

- Added a real horizontal viewport without track compression.
- Pinned the depth track independently from horizontal scrolling.
- Added a draggable full-domain mini-map.
- Added viewport-aware peak-preserving LOD for large LAS curves.
- Added regression tests for pinned tracks, horizontal overflow and LOD budgets.

## Unreleased — Tablet Engine 2.0 Rendering Cache

- added bounded LRU cache for sampled curve geometry;
- added cache hit/miss/eviction metrics;
- skipped redundant curve `setData()` calls for unchanged render keys;
- added 100k, 1M and 5M rendering benchmark scenarios;
- replaced the project plan with a factual GEOLOG-only roadmap.

### Rendering Engine: static cache and dirty tracks

- Added per-track static configuration cache for title, width, grid and axis labels.
- Added explicit dirty reasons for data, style, static state, viewport and layout.
- Added selective curve/static cache invalidation.
- Added partial single-track updates for style, grid, axis label and drag-resize operations.
- Added full/partial refresh metrics and regression tests.


### Selection & Interaction Engine

- Добавлены единые типы выбираемых объектов и результат hit-testing.
- Добавлен менеджер одиночного, множественного и toggle-выделения.
- Выделение дорожек и интервалов подключено к Selection overlay.
- Добавлен общий ограниченный стек Undo/Redo для будущих интерактивных команд.

### Selection & Interaction Engine — второй срез

- Добавлен hit-testing заголовков дорожек и ближайших отображаемых кривых.
- Изменение ширины дорожек и перестановка drag-and-drop записываются в общий Undo/Redo stack.
- Выбор кривой синхронизирован с общей моделью Selection и не пересчитывает геометрию кривых.

### Selection & Interaction Engine — properties, multiselect and context actions

- Added Ctrl/Shift-assisted multi-selection for tracks and curves.
- Added curve selection details in the existing inspector panel.
- Added track header context menu with move, hide, remove, undo and redo actions.
- Kept all context actions synchronized with the shared selection model and interaction command stack.

## Form Engine — data model slice

### Русский
- Добавлена схема форм v1: форма, колонки, дорожки и привязки канонических параметров.
- Добавлены глубинные и временные формы, валидация, JSON-миграция и атомарное хранилище.
- Добавлены неизменяемые заводские шаблоны и редактируемые пользовательские копии.

### Қазақша
- v1 пішін схемасы қосылды: пішін, бағандар, тректер және канондық параметр байланыстары.
- Тереңдік және уақыт пішіндері, тексеру, JSON көшіру және атомдық сақтау қосылды.
- Өзгермейтін зауыттық үлгілер және өңделетін пайдаланушы көшірмелері қосылды.

### English
- Added form schema v1 with forms, columns, tracks and canonical-parameter bindings.
- Added depth/time forms, validation, JSON migration and atomic persistence.
- Added read-only factory templates and editable user copies.

- Added the visual form structure editor with protected factory-template copies, column/track editing, preview and JSON persistence.

### Live Form Preview
- Добавлены draft-состояние формы, живой предпросмотр на рабочем планшете, ручное применение и откат.
- Редактор формы больше не закрывается после сохранения; сценарий «редактировать → применить → сохранить» выполняется в одном окне.
