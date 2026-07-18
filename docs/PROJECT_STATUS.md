# Project Status / Статус проекта / Жоба күйі

## Русский

**Пакет приложения:** 0.6.0  
**Формат проекта:** v15  
**Состояние:** активная разработка; завершена синхронная навигация планшета по глубине и времени.

Готово в текущем инкременте:

- нормализованный справочник из `Editor/Sensors.DB`, `Geolog-055/Sensors.DB` и проверенных LAS-псевдонимов;
- 421 запись параметров и legacy-полей со стабильными ID, каноническими мнемониками, единицами, категориями, семействами, диапазонами и происхождением;
- устойчивое сопоставление мнемоник, включая смешанные кириллические/латинские обозначения;
- просмотр, поиск и подключение внешнего JSON-справочника схемы v1;
- исходная и каноническая мнемоники, фактический и рекомендуемый диапазоны в панели LAS-кривых;
- режимы выбора, рисования и изменения границ интервалов непосредственно на планшете;
- привязка кровли и подошвы к ближайшим отсчётам LAS, preview и отмена жеста через `Esc`;
- валидация через существующий controller и Undo/Redo для мышиных операций;
- выбор вертикальной оси MD/TVD/TVDSS/TIME/DATETIME;
- явная полоса прокрутки, wheel-scroll, `Ctrl+wheel` zoom, панорамирование, переход к значению и полный диапазон;
- синхронное отображение глубинных объектов во временной шкале через TIME↔DEPTH;
- сохранение выбранного индекса в layout v8 и миграция layout v1–v7;
- синхронная локализация RU/KK/EN;
- regression suite: 750 passed, 1 skipped;
- Ruff и MyPy: без ошибок по 155 исходным файлам.

Следующий срез: единая selection-модель экспорта интервалов и подготовка рабочего места корреляции нескольких скважин с общей глубинной/временной навигацией.

## Қазақша

**Қолданба пакеті:** 0.6.0  
**Жоба форматы:** v15  
**Күйі:** белсенді әзірлеу; планшетті тереңдік және уақыт бойынша синхронды навигациялау аяқталды.

Осы инкрементте орындалды:

- `Editor/Sensors.DB`, `Geolog-055/Sensors.DB` және тексерілген LAS бүркеншік аттары негізіндегі анықтамалық;
- тұрақты ID, канондық мнемоника, өлшем бірлігі, санат, жолақ тобы, диапазон және дереккөзі бар 421 жазба;
- кирилл/латын таңбалары аралас мнемоникаларды тұрақты сәйкестендіру;
- v1 сыртқы JSON анықтамалығын қарау, іздеу және қосу;
- LAS қисықтары панелінде бастапқы/канондық мнемоника және нақты/ұсынылатын диапазон;
- планшетте аралықтарды таңдау, сызу және шекарасын өзгерту режимдері;
- төбе мен табанды ең жақын LAS өлшеміне байлау, preview және `Esc` арқылы болдырмау;
- қолданыстағы controller тексеруі және Undo/Redo;
- MD/TVD/TVDSS/TIME/DATETIME тік осін таңдау;
- тік айналдыру жолағы, wheel-scroll, `Ctrl+wheel` zoom, панорамалау, мәнге өту және толық ауқым;
- TIME↔DEPTH арқылы тереңдік объектілерін уақыт шкаласында синхронды көрсету;
- таңдалған индексті layout v8-де сақтау және layout v1–v7 көшіру;
- RU/KK/EN локализациясы синхрондалды;
- regression suite: 750 passed, 1 skipped;
- Ruff және MyPy: 155 бастапқы файл бойынша қатесіз.

Келесі срез: аралықтарды экспорттаудың бірыңғай selection-моделі және ортақ тереңдік/уақыт навигациясы бар бірнеше ұңғыманы корреляциялау жұмыс орнын дайындау.

## English

**Application package:** 0.6.0  
**Project format:** v15  
**Status:** active development; synchronized tablet navigation by depth and time is complete.

Completed in this increment:

- a normalized reference derived from `Editor/Sensors.DB`, `Geolog-055/Sensors.DB`, and validated LAS aliases;
- 421 parameter and legacy-field entries with stable IDs, canonical mnemonics, units, categories, track families, ranges, and provenance;
- robust mnemonic matching including mixed Cyrillic/Latin notation;
- searchable catalog viewer and schema-v1 external JSON connection;
- original/canonical mnemonics plus actual/reference ranges in the LAS curve panel;
- select, draw, and boundary-edit modes directly on the tablet;
- top/bottom snapping to nearest LAS samples, live preview, and `Esc` cancellation;
- validation through the existing controller and Undo/Redo for mouse operations;
- MD/TVD/TVDSS/TIME/DATETIME vertical-axis selection;
- explicit scrollbar, wheel scrolling, `Ctrl+wheel` zoom, panning, go-to, and full range;
- synchronized depth-anchored objects on the time axis through TIME↔DEPTH mapping;
- selected-index persistence in layout v8 and migration of layout v1–v7;
- synchronized RU/KK/EN localization;
- regression suite: 750 passed, 1 skipped;
- Ruff and MyPy: clean across 155 source files.

Next slice: a shared interval-export selection model and groundwork for a multi-well correlation workspace with common depth/time navigation.
