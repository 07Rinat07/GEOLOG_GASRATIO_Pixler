# Project Status / Статус проекта / Жоба күйі

## Русский

**Пакет приложения:** 0.6.0  
**Формат проекта:** v15  
**Состояние:** активная разработка; подключён нормализованный справочник Sensors и завершено прямое редактирование интерпретационных интервалов на планшете.

Готово в текущем инкременте:

- нормализованный справочник из `Editor/Sensors.DB`, `Geolog-055/Sensors.DB` и проверенных LAS-псевдонимов;
- 421 запись параметров и legacy-полей со стабильными ID, каноническими мнемониками, единицами, категориями, семействами, диапазонами и происхождением;
- устойчивое сопоставление мнемоник, включая смешанные кириллические/латинские обозначения;
- просмотр, поиск и подключение внешнего JSON-справочника схемы v1;
- исходная и каноническая мнемоники, фактический и рекомендуемый диапазоны в панели LAS-кривых;
- режимы выбора, рисования и изменения границ интервалов непосредственно на планшете;
- привязка кровли и подошвы к ближайшим отсчётам LAS, preview и отмена жеста через `Esc`;
- валидация через существующий controller и Undo/Redo для мышиных операций;
- синхронная локализация RU/KK/EN;
- regression suite: 743 passed, 1 skipped;
- Ruff и MyPy: без ошибок по 155 исходным файлам.

Следующий срез: единая selection-модель экспорта интервалов и подготовка рабочего места корреляции нескольких скважин.

## Қазақша

**Қолданба пакеті:** 0.6.0  
**Жоба форматы:** v15  
**Күйі:** белсенді әзірлеу; қалыптандырылған Sensors анықтамалығы қосылып, планшеттегі интерпретациялық аралықтарды тікелей өңдеу аяқталды.

Осы инкрементте орындалды:

- `Editor/Sensors.DB`, `Geolog-055/Sensors.DB` және тексерілген LAS бүркеншік аттары негізіндегі анықтамалық;
- тұрақты ID, канондық мнемоника, өлшем бірлігі, санат, жолақ тобы, диапазон және дереккөзі бар 421 жазба;
- кирилл/латын таңбалары аралас мнемоникаларды тұрақты сәйкестендіру;
- v1 сыртқы JSON анықтамалығын қарау, іздеу және қосу;
- LAS қисықтары панелінде бастапқы/канондық мнемоника және нақты/ұсынылатын диапазон;
- планшетте аралықтарды таңдау, сызу және шекарасын өзгерту режимдері;
- төбе мен табанды ең жақын LAS өлшеміне байлау, preview және `Esc` арқылы болдырмау;
- қолданыстағы controller тексеруі және Undo/Redo;
- RU/KK/EN локализациясы синхрондалды;
- regression suite: 743 passed, 1 skipped;
- Ruff және MyPy: 155 бастапқы файл бойынша қатесіз.

Келесі срез: аралықтарды экспорттаудың бірыңғай selection-моделі және бірнеше ұңғыманы корреляциялау жұмыс орнын дайындау.

## English

**Application package:** 0.6.0  
**Project format:** v15  
**Status:** active development; the normalized Sensors reference is connected and direct tablet interval editing is complete.

Completed in this increment:

- a normalized reference derived from `Editor/Sensors.DB`, `Geolog-055/Sensors.DB`, and validated LAS aliases;
- 421 parameter and legacy-field entries with stable IDs, canonical mnemonics, units, categories, track families, ranges, and provenance;
- robust mnemonic matching including mixed Cyrillic/Latin notation;
- searchable catalog viewer and schema-v1 external JSON connection;
- original/canonical mnemonics plus actual/reference ranges in the LAS curve panel;
- select, draw, and boundary-edit modes directly on the tablet;
- top/bottom snapping to nearest LAS samples, live preview, and `Esc` cancellation;
- validation through the existing controller and Undo/Redo for mouse operations;
- synchronized RU/KK/EN localization;
- regression suite: 743 passed, 1 skipped;
- Ruff and MyPy: clean across 155 source files.

Next slice: a shared interval-export selection model and groundwork for the multi-well correlation workspace.
