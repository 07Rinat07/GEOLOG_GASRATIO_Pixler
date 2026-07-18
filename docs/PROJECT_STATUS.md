# Project Status / Статус проекта / Жоба күйі

## Русский

**Пакет приложения:** 0.6.0  
**Формат проекта:** v15  
**Состояние:** активная разработка; завершён рабочий инкремент планшетной визуализации интерпретационных интервалов.

Готово в текущем инкременте:

- отдельная дорожка активной интерпретации на планшете;
- независимые полосы для типов интервалов и корректное отображение наложений разных типов;
- hit-testing по полосе и глубине;
- синхронное выделение между планшетом, менеджером и деревом проекта;
- редактируемая панель свойств: кровля, подошва, тип, подпись, цвет и многострочный комментарий;
- обновление через существующую валидацию и Undo/Redo;
- данные активных интервалов в сводке визирной линии;
- безопасный сброс устаревшего выбора при переключении скважин и открытии проекта;
- синхронная локализация RU/KK/EN;
- полный regression suite: 721 passed, 1 skipped;
- Ruff и MyPy: без ошибок.

Следующий срез: прямое создание интервала и изменение его границ жестами на планшете с preview, привязкой к глубине и отменой операции.

## Қазақша

**Қолданба пакеті:** 0.6.0  
**Жоба форматы:** v15  
**Күйі:** белсенді әзірлеу; интерпретациялық аралықтарды планшетте көрсету инкременті аяқталды.

Осы инкрементте орындалды:

- планшетте белсенді интерпретацияға арналған жеке трек;
- аралық түрлеріне арналған тәуелсіз жолақтар және әртүрлі түрлердің қабаттасуын дұрыс көрсету;
- жолақ пен тереңдік бойынша hit-testing;
- планшет, менеджер және жоба ағашы арасында синхронды таңдау;
- өңделетін қасиеттер панелі: төбе, табан, түр, белгі, түс және көпжолды түсініктеме;
- қолданыстағы тексеру мен Undo/Redo арқылы жаңарту;
- белсенді аралық деректері визир сызығының жиынтығында;
- ұңғыманы ауыстырғанда және жобаны ашқанда ескірген таңдауды қауіпсіз тазарту;
- RU/KK/EN локализациясының синхрондалуы;
- толық regression suite: 721 passed, 1 skipped;
- Ruff және MyPy: қатесіз.

Келесі срез: preview, тереңдікке байланыстыру және операцияны болдырмау арқылы планшетте аралықты тікелей жасау және шекараларын қимылмен өзгерту.

## English

**Application package:** 0.6.0  
**Project format:** v15  
**Status:** active development; the interpretation interval tablet-visualization increment is complete.

Completed in this increment:

- a dedicated tablet track for the active interpretation;
- independent lanes for interval types and correct rendering of different-type overlays;
- lane-and-depth hit testing;
- synchronized selection across the tablet, manager, and project tree;
- an editable property panel for top, bottom, type, label, color, and multiline comment;
- updates routed through the existing validation and Undo/Redo history;
- active interval data in the cursor summary;
- safe stale-selection clearing when switching wells or opening a project;
- synchronized RU/KK/EN localization;
- full regression suite: 721 passed, 1 skipped;
- Ruff and MyPy: clean.

Next slice: direct interval creation and boundary editing with tablet gestures, preview, depth snapping, and cancellable history commands.
