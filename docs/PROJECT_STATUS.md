# Project Status / Статус проекта / Жоба күйі

## Русский

**Пакет приложения:** 0.6.0  
**Формат проекта:** v15  
**Состояние:** активная разработка, рабочий инкремент менеджера интерпретационных интервалов завершён.

Готово в текущем инкременте:

- структура `Project → Well → Interpretation → Intervals`;
- несколько именованных интерпретаций на одну скважину;
- CRUD интервалов: кровля, подошва, тип, подпись, цвет и комментарий;
- проверка диапазона активного dataset и пересечений интервалов одного типа;
- Undo/Redo с обнаружением внешнего конфликта;
- сохранение в проекте v15 и миграция v14 → v15;
- экспорт JSON, CSV и Excel;
- редактор, дерево проекта и строки RU/KK/EN;
- полный regression suite: 714 passed, 1 skipped.

Следующий срез: планшетный трек интерпретаций, hit testing, синхронное выделение и панель свойств.

## Қазақша

**Қолданба пакеті:** 0.6.0  
**Жоба форматы:** v15  
**Күйі:** белсенді әзірлеу, интерпретациялық аралықтар менеджері аяқталды.

Осы инкрементте орындалды:

- `Project → Well → Interpretation → Intervals` құрылымы;
- бір ұңғымаға бірнеше атаулы интерпретация;
- аралық CRUD: төбе, табан, түр, белгі, түс және түсініктеме;
- белсенді dataset диапазонын және бір түрдегі аралықтардың қиылысуын тексеру;
- сыртқы қайшылықты анықтайтын Undo/Redo;
- v15 жобасына сақтау және v14 → v15 көшіру;
- JSON, CSV және Excel экспорты;
- RU/KK/EN редакторы, жоба ағашы және локализация;
- толық regression suite: 714 passed, 1 skipped.

Келесі срез: интерпретация планшет трегі, hit testing, синхронды таңдау және қасиеттер панелі.

## English

**Application package:** 0.6.0  
**Project format:** v15  
**Status:** active development; the interpretation interval manager increment is complete.

Completed in this increment:

- `Project → Well → Interpretation → Intervals` hierarchy;
- multiple named interpretations per well;
- interval CRUD with top, bottom, type, label, color, and comment;
- active-dataset bounds and same-type overlap validation;
- conflict-aware Undo/Redo;
- project v15 persistence and v14 → v15 migration;
- JSON, CSV, and Excel export;
- RU/KK/EN editor, project tree, and localization;
- full regression suite: 714 passed, 1 skipped.

Next slice: interpretation tablet track, hit testing, synchronized selection, and property panel.
