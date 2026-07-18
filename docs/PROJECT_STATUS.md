# Project Status / Статус проекта / Жоба күйі

## Русский

**Формат проекта:** v15  
**Формат планшетной компоновки:** v8  
**Состояние:** активная разработка; начат Tablet Engine 2.0.

Текущий завершённый срез:

- добавлена единая модель навигации `TabletCamera` для глубины и времени;
- прокрутка ограничивается фактическим диапазоном данных;
- `Ctrl+колесо` масштабирует относительно точки под курсором;
- работают `Home`, `End`, `PageUp`, `PageDown`, `↑`, `↓`;
- реализовано перемещение средней кнопкой и `Space + ЛКМ`;
- все дорожки используют единое видимое окно;
- сохранена совместимость с существующими layout v8 и проектами v15.

Следующий срез: горизонтальный viewport дорожек, мини-карта диапазона, peak-preserving LOD и измеримые performance budgets.

## Қазақша

**Жоба форматы:** v15  
**Планшет орналасуы:** v8  
**Күйі:** белсенді әзірлеу; Tablet Engine 2.0 басталды.

Аяқталған срез:

- тереңдік пен уақыт үшін ортақ `TabletCamera`;
- айналдыру деректер ауқымымен шектеледі;
- `Ctrl+дөңгелек` курсор тұрған мәнге қатысты масштабтайды;
- `Home`, `End`, `PageUp`, `PageDown`, `↑`, `↓` жұмыс істейді;
- ортаңғы батырмамен және `Space + сол батырма` арқылы жылжыту бар;
- барлық жолақтар бір көрінетін терезені қолданады;
- layout v8 және project v15 үйлесімділігі сақталды.

Келесі срез: көлденең viewport, диапазон мини-картасы, шыңдарды сақтайтын LOD және өнімділік бюджеттері.

## English

**Project format:** v15  
**Tablet layout format:** v8  
**Status:** active development; Tablet Engine 2.0 has started.

Completed slice:

- common `TabletCamera` for depth and time;
- scrolling clamps to the actual data domain;
- `Ctrl+wheel` zooms around the cursor value;
- `Home`, `End`, `PageUp`, `PageDown`, `Up`, and `Down` work;
- middle-button and `Space + left button` panning;
- every track shares one visible window;
- layout v8 and project v15 compatibility retained.

Next slice: horizontal track viewport, range minimap, peak-preserving LOD, and measurable performance budgets.

## Tablet Engine 2.0: второй срез

Завершены горизонтальный viewport, закреплённая дорожка глубины, мини-карта полного диапазона и peak-preserving LOD. Следующий срез: кэш геометрии, частичная перерисовка и performance-budget для файлов с миллионами отсчётов.
