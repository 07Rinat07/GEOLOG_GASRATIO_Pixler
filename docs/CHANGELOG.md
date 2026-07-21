# 0.7.6 — Safe LAS Editor

- added a separate Editor menu and visible LAS Editor toolbar button (`Ctrl+Alt+E`);
- grouped LAS creation, table editing, depth repair, resampling, external-curve insertion, splicing and export;
- external insertion now creates and exports a new dataset instead of modifying the receiver;
- merge results are saved as a new LAS and both inputs remain unchanged;
- descending depth is normalized in memory for insertion and splicing;
- duplicate/vendor mnemonics such as `GK:1` and `GK:2` are converted to `GK_1` and `GK_2`;
- Cyrillic and separator-heavy mnemonics receive deterministic ASCII output names;
- validated against a real CP866 GIS LAS with negative STEP and duplicate GK curves.

# 0.7.5 — KazGeology reference blank

- Added an A3 landscape Masterlog preset based on the supplied geological-technological survey reference.
- Added two optional image placeholders for contractor and customer logos.
- Empty optional image slots render a localized upload prompt and no longer raise a missing-asset preflight warning.
- Added editable region, district/block, target formation, customer representative and shift-personnel header fields.
- Added a standalone importable `.masterlog.json` package and synchronized RU/KK/EN documentation.

# 0.7.4 — 2026-07-21

## Читаемый Excel-экспорт LAS-таблицы

### Русский

- верхняя строка листа `Data` теперь показывает понятное название параметра, исходную/каноническую мнемонику и единицу измерения в одном многострочном заголовке;
- добавлен лист `Parameters` с расшифровкой всех экспортированных колонок, описанием из LAS, признаком распознавания, уверенностью и методом сопоставления;
- неизвестная мнемоника больше не маскируется под понятное название и явно помечается как «Не распознано»;
- распространённые газовые компоненты C1–C5, iC4/nC4, iC5/nC5, TG, H2S и CO2 получают человекочитаемые названия;
- текст LAS очищается от типичных ошибок кодировки перед записью в XLSX;
- язык заголовков соответствует текущему языку интерфейса RU/KK/EN; числовые значения остаются числами Excel.

### Қазақша

- `Data` парағының тақырыбы түсінікті атауды, бастапқы/канондық мнемониканы және өлшем бірлігін көрсетеді;
- `Parameters` парағында барлық бағандардың түсіндірмесі, LAS сипаттамасы, анықтау сенімділігі мен әдісі беріледі;
- белгісіз параметр «Анықталмаған параметр» деп нақты белгіленеді;
- тақырыптар интерфейс тілімен RU/KK/EN экспортталады, сандық мәндер Excel саны болып қалады.

### English

- the `Data` header now combines a readable name, original/canonical mnemonic and unit;
- a `Parameters` sheet explains every exported column, LAS description, resolution state, confidence and match method;
- unresolved mnemonics are explicitly marked instead of being presented as readable names;
- common gas components receive readable chemical names;
- typical LAS mojibake is cleaned before writing XLSX; headers follow the active RU/KK/EN UI language while numeric cells remain numeric.

# 0.7.3 — 2026-07-21

## Изоляция LAS-скважин и правильный якорь повёрнутого текста

### Русский

- обычная команда «Открыть LAS» больше не присоединяет файл к ранее активной скважине; каждый открытый LAS получает отдельную чистую рабочую скважину;
- литология, шламограмма, ЛБА, кальциметрия, стратиграфия, описания, интерпретации и глубинные обозначения предыдущей скважины не переносятся в новый LAS;
- старые несохранённые данные остаются только в своей скважине текущего проекта и могут быть выбраны в дереве до закрытия проекта;
- намеренное объединение данных выполняется отдельными командами вставки внешнего LAS или сращивания dataset;
- переключение после импорта проходит через общий путь `_show_current_dataset`, который очищает все well-scoped слои экрана;
- исправлен якорь текста 0°/±90°: положение у кровли, по центру и у подошвы относится ко всей подписи, поэтому вертикальный текст больше не выходит за прямоугольник интервала;
- одинаковая логика применена к планшету, заголовкам формы, WYSIWYG-шапке, preview, PDF и физической печати.

### Қазақша

- «LAS ашу» енді файлды бұрынғы белсенді ұңғымаға қоспайды; әр LAS үшін таза жеке ұңғыма жұмыс кеңістігі жасалады;
- алдыңғы ұңғыманың литологиясы, шламограммасы, ЛБА, кальциметриясы, стратиграфиясы, сипаттамалары және белгілері жаңа LAS-қа көшпейді;
- біріктіру тек сыртқы LAS енгізу немесе dataset біріктіру командалары арқылы орындалады;
- 0°/±90° мәтін якорі түзетілді: жазу төбе/орта/табан режимінде толықтай аралық ішінде қалады.

### English

- normal Open LAS no longer attaches a file to the previously active well; every opened LAS receives a clean, separate well workspace;
- lithology, cuttings, LBA, calcimetry, stratigraphy, descriptions, interpretations and depth symbols cannot leak from the previous well;
- intentional combination remains available through the external-LAS insertion and dataset-merge workflows;
- post-import activation now uses the common dataset switch path, clearing every well-scoped visual layer;
- corrected 0°/±90° text anchoring so top, centre and bottom placement keeps the entire label inside its interval across tablet, constructor, preview, PDF and print.

# Unreleased — unified reports and manual description templates

### Русский

- в план добавлен обязательный единый интервальный отчёт по литологии, шламу, ручным описаниям, ЛБА, кальциметрии, стратиграфии, газам и технологии;
- запланированы PDF, DOCX, XLSX, CSV/TSV и HTML, вкладка «Отчёты» в Конструкторе, preview и preflight;
- зафиксировано различие реального нуля и отсутствующего измерения, хранение единиц, формул, версий и покрытия;
- автоматическое описание пород запрещено: только ручной ввод или явная вставка шаблона.

### Қазақша

- жоспарға литология, шлам, қол сипаттамасы, ЛБА, кальциметрия, стратиграфия, газ және технология бойынша бірыңғай аралық есеп қосылды;
- PDF, DOCX, XLSX, CSV/TSV және HTML, Конструктордағы «Есептер» қойындысы, preview және preflight жоспарланды;
- нақты нөл мен жоқ өлшем ажыратылып, бірлік, формула, нұсқа және қамту сақталады;
- жыныс сипаттамасы тек қолмен не нақты шаблон енгізу арқылы толтырылады.

### English

- added a mandatory unified interval-report stage for lithology, cuttings, manual descriptions, LBA, calcimetry, stratigraphy, gas and drilling data;
- planned PDF, DOCX, XLSX, CSV/TSV and HTML, a Reports tab in the Constructor, preview and preflight;
- specified zero-vs-missing semantics plus units, formula versions, provenance and coverage;
- automatic rock-description fallback is forbidden; text is manual or explicitly inserted from a template.

# 0.7.2 — 2026-07-21

## Точное применение переданных литотипов

- все 17 исторических базовых ID пород переназначены на точные BMP из `Litol_Bmp(2).zip` и `Litol2_Bmp(2).zip`;
- старые ключи штриховок в сохранённых проектах автоматически разрешаются в соответствующие BMP, поэтому миграция пользовательских проектов не требуется;
- добавлен device-space renderer для планшета: маленькая текстура повторяется в исходном пиксельном масштабе и не растягивается при зуме глубины;
- preview, PDF и физическая печать используют 96-DPI физический масштаб текстуры: BMP не растягивается в миллиметровый блок и сохраняет одинаковую читаемую плотность на разных устройствах;
- литология, шламограмма, миниатюры справочника, легенды шапки, preview, PDF и печать используют один и тот же рисунок;
- код породы и процент больше не закрывают рисунок по умолчанию; подписи можно отдельно включить в редакторе дорожки или формы;
- layout планшета обновлён до версии 12, схема формы — до версии 3 с безопасной миграцией старых файлов;
- проверка: `988 passed, 1 skipped`; Ruff и compileall без ошибок.

# 0.7.1 — 2026-07-21

### Русский

- направление и положение текста добавлены в стратиграфические интервалы, заголовки колонок/дорожек формы, текст и динамические поля шапки;
- доступны горизонтальный режим, 90° снизу вверх, 90° сверху вниз и размещение у верха, по центру или у низа;
- один механизм отрисовки применяется в планшете, WYSIWYG-preview, PDF и физической печати;
- 117 переданных BMP-литотипов подключены как заводской слой общего справочника без копирования в каждый проект;
- реальные миниатюры и полный стандартный набор доступны в редакторах литологии и шламограммы;
- добавлен элемент шапки `lithotype_swatch` с выбором рисунка, подписи, поворота и положения;
- заводской литотип можно переопределить в проекте и затем сбросить, пользовательский — добавить, изменить или удалить;
- preflight проверяет отсутствующие литотипы в отдельных образцах и ручных легендах;
- старые проекты и формы используют безопасные значения `horizontal` и `center`.

### Қазақша

- мәтін бағыты мен орны стратиграфиялық аралықтарға, пішін бағандары/жолдарының тақырыптарына және тақырып мәтіндері мен динамикалық өрістеріне қосылды;
- көлденең, төменнен жоғары 90°, жоғарыдан төмен 90° және жоғары/орта/төмен орналастыру режимдері бар;
- бір көрсету механизмі планшетте, WYSIWYG preview-де, PDF пен физикалық баспада қолданылады;
- берілген 117 BMP литотип әр жобаға көшірілмей, жалпы анықтамалықтың зауыттық қабаты ретінде қосылды;
- литология мен шламограмма редакторларында нақты миниатюралар және толық стандартты жинақ бар;
- тақырыпқа сурет, жазу, бұру және орнын таңдауға болатын `lithotype_swatch` элементі қосылды;
- зауыттық литотипті жобада қайта анықтап, кейін қалпына келтіруге, ал пайдаланушы литотипін қосуға және өзгертуге болады;
- preflight жеке үлгілер мен қолмен жасалған аңыздардағы жоқ литотиптерді тексереді;
- ескі жобалар мен пішіндер `horizontal` және `center` қауіпсіз мәндерін қолданады.

### English

- text direction and position now apply to stratigraphy intervals, form column/track captions, header text, and dynamic fields;
- supported modes are horizontal, 90° bottom-to-top, 90° top-to-bottom, with near-top, centre, or near-bottom placement;
- tablet, WYSIWYG preview, PDF, and physical printing share one presentation implementation;
- all 117 supplied BMP lithotypes are exposed as a factory catalog layer without copying them into each project;
- lithology and cuttings editors show the full standard set with real pattern thumbnails;
- added the `lithotype_swatch` header element with pattern, label, rotation, and placement controls;
- factory lithotypes may be overridden and reset, while project lithotypes may be added and edited;
- preflight validates missing lithotypes in swatches and manual legends;
- legacy projects and forms use safe `horizontal` and `center` defaults.
# Unreleased — LAS Editor 2: merge, external insertion, pencil, and spreadsheet

### Русский

- добавлена отдельная возрастающая копия убывающего LAS с сохранением оригинала;
- прогрессивное сращивание сохраняет старые значения по умолчанию, заполняет пропуски новым LAS и поддерживает альтернативные политики перекрытия;
- заголовки, параметры, дополнительные индексы и несовместимые одноимённые кривые сохраняются, результат получает `MERGE_MANIFEST`;
- добавлена команда вставки выбранных данных непосредственно из внешнего LAS-файла;
- поддержаны частичное перекрытие, глубины `m/ft/cm/mm`, убывающий внешний индекс, разрывы и `NULL/NaN`;
- вставка сохраняет `EXTERNAL_LAS_IMPORT_*` manifest и поддерживает защищённые Undo/Redo;
- графический карандаш и пакетные табличные изменения синхронно пересчитывают существующие зависимые расчёты;
- LAS-таблица поддерживает системный `Ctrl+C/Ctrl+V`, многоячеечные блоки, очистку и экспорт XLSX/TSV/CSV;
- добавлены целевые регрессионные тесты внешней вставки; полный прогон: `952 passed, 1 skipped`; Ruff и compileall без ошибок;
- документация синхронизирована на RU/KK/EN.

### Қазақша

- кемитін тереңдігі бар LAS үшін бастапқы файлды өзгертпейтін өсу реті көшірмесі қосылды;
- прогрессивті біріктіру ескі мәндерді сақтайды, бос орындарды жаңа LAS-пен толтырады және балама қабаттасу саясаттарын қолдайды;
- тақырыптар, параметрлер, қосымша индекстер және сәйкес келмейтін аттас қисықтар сақталып, `MERGE_MANIFEST` жазылады;
- сыртқы LAS файлынан таңдалған қисықтарды ағымдағы dataset-ке тікелей енгізу қосылды;
- ішінара қабаттасу, `m/ft/cm/mm`, кемитін индекс, үзілістер және `NULL/NaN` қолдауы енгізілді;
- енгізу `EXTERNAL_LAS_IMPORT_*` manifest-ін сақтайды және қорғалған Undo/Redo береді;
- графикалық қарындаш пен кестелік топтық өзгерістер тәуелді есептерді синхронды қайта есептейді;
- LAS кестесі жүйелік `Ctrl+C/Ctrl+V`, көп ұяшықты блоктар, тазалау және XLSX/TSV/CSV экспортын қолдайды;
- сыртқы енгізу тесттері қосылды; толық іске қосу: `952 passed, 1 skipped`; Ruff және compileall қатесіз өтті;
- RU/KK/EN құжаттамасы жаңартылды.

### English

- added an ascending-depth copy for descending LAS files while preserving the original;
- progressive merge preserves old values by default, fills gaps from the new LAS, and supports alternate overlap policies;
- headers, parameters, additional indexes, and incompatible duplicate curves are retained with a `MERGE_MANIFEST`;
- added direct insertion of selected curves from an external LAS file into the current dataset;
- supported partial overlap, `m/ft/cm/mm`, descending external indexes, gaps, and `NULL/NaN`;
- insertion stores an `EXTERNAL_LAS_IMPORT_*` manifest and provides guarded Undo/Redo;
- pencil and spreadsheet edits synchronously recalculate existing dependent outputs;
- the LAS table supports system `Ctrl+C/Ctrl+V`, multi-cell blocks, clearing, and XLSX/TSV/CSV exports;
- added focused external-insertion regression tests; full run: `952 passed, 1 skipped`; Ruff and compileall pass;
- synchronized RU/KK/EN documentation.

## Unreleased — editable form captions and working stratigraphy

### Русский

- на любой дорожке планшета добавлено контекстное действие «Редактировать всё в дорожке…»;
- редактируются название дорожки, объединённый заголовок раздела, ширина, подпись оси X, порядок параметров, подписи, цвета, стили, шкалы и диапазоны;
- быстрые команды переименования дорожки и раздела доступны по правой кнопке;
- замена LAS-кривых больше не сбрасывает пользовательское название дорожки;
- в основную панель добавлены кнопки редактора выбранной дорожки, режима стратиграфии и менеджера стратиграфических интервалов;
- добавлен проектно-расширяемый справочник основных стратиграфических единиц с RU/KK/EN, кодами и цветами;
- заводские записи можно переопределять и сбрасывать, местные свиты/пачки/горизонты добавляются в проект;
- дорожка «Стратиграфия» поддерживает `Shift + ЛКМ`, отдельный режим, preview, `Esc`, двойной щелчок и контекстное редактирование;
- интервалы и проектный справочник сохраняются вместе с проектом;
- полный регрессионный запуск: `932 passed, 1 skipped`; Ruff и compileall проходят без ошибок;
- документация обновлена синхронно на RU/KK/EN.

### Қазақша

- планшеттегі кез келген жолға «Жол ішін толық өңдеу…» контекстік әрекеті қосылды;
- жол атауы, біріктірілген бөлім атауы, ені, X осі, параметр тәртібі, жазулар, түс, стиль, шкала және диапазон өңделеді;
- жол мен бөлімді жылдам қайта атау оң жақ батырмада қолжетімді;
- LAS қисықтарын ауыстыру пайдаланушы жол атауын енді жоймайды;
- негізгі панельге таңдалған жол редакторы, стратиграфия режимі және интервал менеджері қосылды;
- RU/KK/EN атаулары, кодтары және түстері бар жобалық стратиграфиялық анықтамалық енгізілді;
- зауыттық жазбаларды өзгерту/қалпына келтіру және жергілікті бірліктерді қосу мүмкін;
- «Стратиграфия» жолағы `Shift + ЛКМ`, жеке режим, preview, `Esc`, екі рет шерту және контекстік өңдеуді қолдайды;
- аралықтар мен анықтамалық жоба ішінде сақталады;
- толық регрессиялық іске қосу: `932 passed, 1 skipped`; Ruff және compileall қатесіз өтті;
- құжаттама RU/KK/EN тілдерінде синхрондалды.

### English

- added an “Edit everything in track…” context action to every tablet track;
- track title, merged section title, width, X-axis caption, parameter order, captions, colours, styles, scales, and ranges are editable;
- quick track and section renaming is available from the right-click menu;
- replacing LAS curves no longer overwrites a user-defined track title;
- added toolbar buttons for editing the selected track, stratigraphy drawing mode, and interval management;
- added a project-extensible reference catalog with RU/KK/EN names, codes, and colours;
- factory entries can be overridden/reset and local formations/members/horizons can be added;
- the Stratigraphy track supports `Shift + left drag`, a dedicated mode, preview, `Esc`, double-click, and context editing;
- well intervals and project catalog overrides are saved with the project;
- full regression run: `932 passed, 1 skipped`; Ruff and compileall pass without errors;
- synchronized RU/KK/EN documentation.

## Unreleased — GeoData reference editors and relative gas composition

### Русский

- глубинная форма приведена к структуре предоставленного рабочего экрана GeoData: «Геология», «Технология» и «Газовые данные» на одной глубинной координате;
- абсолютная газовая колонка содержит `TG_CALC`, `C1`, `C2`;
- добавлены кривые относительного состава `C1_REL`…`C5_REL` в процентах от суммы доступных компонентов;
- строка, где все газовые компоненты являются `NULL/NaN`, больше не превращается в ложный `TG_CALC = 0`;
- единый редактор шламовой пробы переработан по предоставленным окнам GeoData: интервал, четыре породы с суммой 100%, цветовые варианты ЛБА, интенсивность 1–5, кальцит, доломит и автоматически рассчитанный остаток;
- существующая проба повторно открывается из шламограммы, ЛБА, кальциметрии или описания и обновляется по прежнему `sample_id`;
- в окне редактирования литологии добавлено удаление существующего интервала;
- текстовый редактор поддерживает шрифт, размер, цвет, фон/выделение, верхний/нижний индекс, выравнивание, символы и изображения;
- интерфейс редакторов адаптируется к доступной области экрана;
- дорожка ЛБА приведена к трёхчастной структуре GeoData «Баллы / Цвет / Битум»: размер условного кольца соответствует интенсивности 1–5, цвет свечения и класс ЛБ/МБ/МСБ/СБ/САБ отображаются раздельно;
- названия технологических параметров локализованы во всех трёх языковых шаблонах;
- полный регрессионный запуск: `925 passed, 1 skipped`; Ruff и compileall проходят без ошибок;
- документация синхронизирована на русском, казахском и английском языках.

### Қазақша

- тереңдік пішіні берілген GeoData жұмыс экранының құрылымына келтірілді: «Геология», «Технология» және «Газ деректері» бір тереңдік координатасында;
- абсолюттік газ бағанында `TG_CALC`, `C1`, `C2` бар;
- қолжетімді компоненттер қосындысының пайызы ретінде `C1_REL`…`C5_REL` салыстырмалы құрам қисықтары қосылды;
- барлық газ компоненттері `NULL/NaN` болған жол енді жалған `TG_CALC = 0` мәніне айналмайды;
- шлам үлгісінің бірыңғай редакторы GeoData терезелерінің үлгісі бойынша қайта жасалды: аралық, қосындысы 100% болатын төрт жыныс, ЛБА түсті түрлері, 1–5 қарқындылық, кальцит, доломит және автоматты қалдық;
- бар үлгі шламограмма, ЛБА, кальциметрия немесе сипаттама бағанынан қайта ашылып, сол `sample_id` бойынша жаңартылады;
- литологияны өңдеу терезесіне аралықты жою қосылды;
- мәтін редакторы қаріп, өлшем, түс, фон/белгілеу, жоғарғы/төменгі индекс, туралау, таңбалар мен суреттерді қолдайды;
- редакторлар экранның қолжетімді аймағына бейімделеді;
- ЛБА жолағы GeoData-дағы «Балл / Түс / Битум» үш бөлімді құрылымына келтірілді: шартты сақина өлшемі 1–5 қарқындылығына сәйкес, жарқырау түсі мен ЛБ/МБ/МСБ/СБ/САБ класы бөлек көрсетіледі;
- технологиялық параметр атаулары үш тілдік үлгіде де локализацияланды;
- толық регрессиялық іске қосу: `925 passed, 1 skipped`; Ruff және compileall қатесіз өтті;
- құжаттама орыс, қазақ және ағылшын тілдерінде синхрондалды.

### English

- aligned the depth workspace with the supplied GeoData working-screen structure: Geology, Technology, and Gas Data on one depth coordinate;
- the absolute-gas column now contains `TG_CALC`, `C1`, and `C2`;
- added relative-composition curves `C1_REL`…`C5_REL` as percentages of the available component sum;
- a row where every gas component is `NULL/NaN` no longer becomes a false `TG_CALC = 0`;
- redesigned the unified cuttings-sample editor from the supplied GeoData dialogs: interval, four rocks totaling 100%, colour-coded LBA types, intensity 1–5, calcite, dolomite, and automatic residue;
- an existing sample can be reopened from Cuttings, LBA, Calcimetry, or Description and is updated under the same `sample_id`;
- added deletion of an existing lithology interval from its edit dialog;
- the text editor supports font, size, colour, highlight/background, superscript/subscript, alignment, symbols, and images;
- editor dialogs adapt to the available screen area;
- changed the LBA track to the three-part GeoData layout “Score / Color / Bitumen”; symbol size follows intensity 1–5, while fluorescence color and LB/MB/MSB/SB/SAB class are shown separately;
- localized technology parameter names in all three language templates;
- full regression run: `925 passed, 1 skipped`; Ruff and compileall pass without errors;
- synchronized Russian, Kazakh, and English documentation.

## Unreleased — lithology Shift-drag interval editor

### Русский

- в дорожке «Литология» `Shift + левая кнопка мыши` создаёт новый интервал протягиванием от кровли до подошвы;
- во время жеста отображается полупрозрачный пунктирный preview, `Esc` отменяет операцию;
- после отпускания открывается компактное окно только с границами и выбором одной породы;
- границы можно исправить вручную до подтверждения;
- пересечения и выход за диапазон LAS проверяются существующим `LithologyController`;
- после `ОК` интервал сразу отображается на планшете, проект помечается изменённым, а кнопка сохранения в панели получила стандартную иконку дискеты.

### Қазақша

- «Литология» жолағында `Shift + тінтуірдің сол жақ батырмасы` арқылы төбеден табанға дейін жаңа аралық созылады;
- әрекет кезінде жартылай мөлдір пунктир preview көрсетіледі, `Esc` әрекетті тоқтатады;
- батырма жіберілгенде тек шекаралар мен бір тау жынысын таңдауға арналған ықшам терезе ашылады;
- растауға дейін шекараларды қолмен түзетуге болады;
- қиылысу және LAS диапазонынан шығу `LithologyController` арқылы тексеріледі;
- `ОК` басылғаннан кейін аралық планшетте бірден көрсетіліп, жоба өзгертілген деп белгіленеді, ал сақтау батырмасына дискета белгішесі қосылды.

### English

- `Shift + left mouse drag` in a Lithology track creates a new top-to-bottom interval;
- a translucent dashed preview is shown during the gesture and `Esc` cancels it;
- releasing the mouse opens a compact editor containing only the boundaries and one rock-type selector;
- boundaries remain editable before confirmation;
- overlap and LAS-range checks reuse the existing `LithologyController`;
- after `OK` the interval is rendered immediately, the project becomes dirty, and the toolbar save action now has a standard diskette icon.

## Unreleased — faithful Masterlog, calcimetry/LBA, and curve gaps

### Русский

- геолого-геохимический Masterlog пересобран одной формой по переданному эталону: стратиграфия, WOB/ROP/ДМК/DEXP, глубина, шламограмма, ЛБА, кальциметрия, литология, C1–C5/TG и описание пород;
- экранная форма связана с печатной шапкой `geological_geochemical`;
- исправлена семантика NULL/0: LAS NULL/NaN разрывает линию, настоящий ноль остаётся на нулевой линии;
- pyqtgraph получает `connect="finite"`, а LOD/downsampling выполняется по отдельным непрерывным сегментам;
- кальциметрия показывает CaCO₃, CaMg(CO₃)₂ и остаток по интервалу пробы, без интерполяции между пробами;
- ЛБА отображает тип битумоида и интенсивность 1–5 условными интервальными знаками;
- добавлено семантическое сопоставление vendor-каналов ДМК, DEXP, кальцита и доломита;
- исправлено двойное масштабирование шрифтов печатного renderer-а.

### Қазақша

- геологиялық-геохимиялық Masterlog берілген эталон бойынша біртұтас пішінге қайта жиналды: стратиграфия, WOB/ROP/ДМК/DEXP, тереңдік, шламограмма, ЛБА, кальциметрия, литология, C1–C5/TG және жыныс сипаттамасы;
- экран пішіні `geological_geochemical` баспа тақырыбымен байланыстырылды;
- NULL/0 семантикасы түзетілді: LAS NULL/NaN сызықты үзеді, нақты нөл нөлдік сызықта қалады;
- pyqtgraph `connect="finite"` алады, ал LOD/downsampling әр үздіксіз сегмент үшін бөлек орындалады;
- кальциметрия CaCO₃, CaMg(CO₃)₂ және қалдықты сынама аралығы бойынша, сынамалар арасын интерполяцияламай көрсетеді;
- ЛБА битумоид түрі мен 1–5 қарқындылықты аралық шартты белгілермен көрсетеді;
- ДМК, DEXP, кальцит және доломит vendor-арналарын семантикалық сәйкестендіру қосылды;
- баспа renderer қарпінің қосарланған масштабталуы түзетілді.

### English

- rebuilt the geological-geochemical Masterlog as one coherent form from the supplied reference: stratigraphy, WOB/ROP/DMC/DEXP, depth, cuttings, LBA, calcimetry, lithology, C1–C5/TG, and rock descriptions;
- linked the screen form to the `geological_geochemical` print header;
- fixed NULL/zero semantics: LAS NULL/NaN breaks the line, while a real zero remains on the zero baseline;
- pyqtgraph receives `connect="finite"`, and LOD/downsampling runs independently per continuous segment;
- calcimetry displays CaCO₃, CaMg(CO₃)₂, and residue per sample interval without interpolating between samples;
- LBA displays bitumen type and intensity 1–5 as interval symbols;
- added semantic vendor-channel matching for DMC, DEXP, calcite, and dolomite;
- fixed double font scaling in the print renderer.

## Unreleased — human-readable LAS table headers

### Русский

- табличный редактор по умолчанию показывает понятное локализованное название, исходную
  мнемонику, каноническое соответствие и единицу, например `S800 → C1`;
- добавлены режимы «Понятные + LAS», «Только понятные» и «Только LAS»;
- ширина колонок автоматически подбирается по самой длинной строке заголовка с безопасными
  пределами и остаётся доступной для ручного изменения;
- tooltip заголовка показывает описание LAS, исходную/каноническую мнемонику, единицу,
  уверенность, метод, evidence и provenance;
- неопознанный канал не переименовывается молча: используется исходное описание или явная
  отметка «Не распознано»;
- исходные LAS-мнемоники и lossless-экспорт не изменяются;
- полный регрессионный прогон: `888 passed, 1 skipped`; Ruff проходит без ошибок.

### Қазақша

- кестелік редактор әдепкіде түсінікті локализацияланған атауды, бастапқы мнемониканы,
  канондық сәйкестікті және өлшем бірлігін көрсетеді, мысалы `S800 → C1`;
- «Түсінікті + LAS», «Тек түсінікті» және «Тек LAS» режимдері қосылды;
- баған ені тақырыптың ең ұзын жолына қарай қауіпсіз шектерде автоматты түрде есептеледі және
  қолмен өзгертуге болады;
- тақырып tooltip-і LAS сипаттамасын, бастапқы/канондық мнемониканы, өлшем бірлігін,
  сенімділікті, әдісті, evidence және provenance мәндерін көрсетеді;
- танылмаған арна жасырын қайта аталмайды: бастапқы сипаттамасы немесе «Танылмады» белгісі
  көрсетіледі;
- бастапқы LAS мнемоникалары мен lossless экспорт өзгермейді;
- толық регрессиялық тексеру: `888 passed, 1 skipped`; Ruff қатесіз өтеді.

### English

- the table editor now defaults to a localized friendly name, original mnemonic, canonical
  mapping, and unit, for example `S800 → C1`;
- added Friendly + LAS, Friendly only, and LAS only modes;
- column width is derived from the longest header line within safe limits and remains manually
  resizable;
- header tooltips show the LAS description, original/canonical mnemonic, unit, confidence,
  method, evidence, and provenance;
- unresolved channels are never silently renamed: their source description or an explicit
  Unrecognized marker is shown;
- original LAS mnemonics and lossless export remain unchanged;
- full regression suite: `888 passed, 1 skipped`; Ruff passes without errors.

## Unreleased — semantic LAS parameter resolver

### Русский

- добавлен единый resolver базовых LAS-параметров, независимый от порядка колонок;
- используются исходная/каноническая мнемоника, Sensors-каталог, RU/KK/EN-описание, химическая формула и единица;
- поддерживаются кириллические омоглифы (`С1` → `C1`), дефисы, пробелы, подчёркивания и служебные суффиксы;
- Gas Ratio больше не зависит от локального списка точных имён `C1/C2/C3`;
- `%`, `ppm`, `ppb` и доли приводятся к общей процентной шкале;
- одинаково уверенные дублирующие каналы блокируются как неоднозначные;
- при импорте сохраняется исходная мнемоника, а каноническая заполняется только при уверенном распознавании;
- полный регрессионный прогон: `884 passed, 1 skipped`; Ruff проходит без ошибок.

### Қазақша

- баған ретіне тәуелсіз бірыңғай LAS параметр resolver қосылды;
- бастапқы/канондық мнемоника, Sensors анықтамалығы, RU/KK/EN сипаттамасы, химиялық формула және өлшем бірлігі қолданылады;
- кирилл омоглифтері (`С1` → `C1`), дефис, бос орын, астын сызу және қызметтік суффикстер қолдау табады;
- Gas Ratio енді `C1/C2/C3` дәл атауларының жергілікті тізіміне тәуелді емес;
- `%`, `ppm`, `ppb` және үлестер бірыңғай пайыздық шкалаға келтіріледі;
- бірдей сенімді қайталанатын арналар екіұшты ретінде тоқтатылады;
- импорт кезінде бастапқы мнемоника сақталып, канондық атау тек сенімді танылғанда жазылады;
- толық регрессиялық тексеру: `884 passed, 1 skipped`; Ruff қатесіз өтеді.

### English

- added one semantic LAS parameter resolver independent of column order;
- matching uses original/canonical mnemonics, the Sensors catalog, RU/KK/EN descriptions, chemical formulas, and units;
- supports Cyrillic homoglyphs (`С1` → `C1`), hyphens, spaces, underscores, and acquisition suffixes;
- Gas Ratio no longer depends on a local list of exact `C1/C2/C3` names;
- `%`, `ppm`, `ppb`, and fractions are normalized to one percent scale;
- equally confident duplicate channels are blocked as ambiguous;
- import preserves the original mnemonic and assigns a canonical name only at sufficient confidence;
- full regression suite: `884 passed, 1 skipped`; Ruff passes without errors.

## Unreleased — universal Print and Export Center

### Русский

- добавлен единый «Центр печати и экспорта» для текущего графика, планшета и выбранной формы из менеджера форм;
- поддерживаются физический системный принтер, PDF, PNG, JPEG/JPG, TIFF, BMP, WebP и SVG;
- доступны A4, A3, пользовательский размер и рулон, книжная/альбомная ориентация, отдельные поля страницы, 72–600 DPI и качество JPEG/WebP;
- растровые файлы создаются в реальном размере бумаги при выбранном DPI, а не как скриншот окна;
- предварительный просмотр, физическая печать, PDF, SVG и изображения используют общий page renderer;
- для форм печатаются все видимые колонки, включая находящиеся вне горизонтального viewport, с восстановлением экранных ширин;
- настройки страницы, многостраничного диапазона и качества сохраняются отдельно для активного инженерного профиля;
- добавлены режимы текущего, полного и пользовательского диапазона, интервал на страницу, перекрытие, повтор заголовков, диапазон и нумерация страниц;
- PDF и физический принтер создают один многостраничный документ, растровые/SVG-форматы — нумерованные файлы страниц;
- строгий Unicode preflight проверяет RU/KK/EN, инженерные символы, отсутствующие глифы и повреждённую перекодировку; для `QPrinter` включено внедрение шрифтов;
- начальный глубинный viewport новой формы установлен в `50 м`, сохранённый диапазон имеет приоритет;
- добавлена кнопка «Печать / экспорт» непосредственно в менеджер форм;
- регрессионные проверки изменений: `93 passed`; полный набор assertions: `872 passed, 1 skipped`; Ruff проходит без ошибок.

### Қазақша

- ағымдағы графикке, планшетке және пішіндер менеджерінде таңдалған пішінге арналған бірыңғай «Басып шығару және экспорт орталығы» қосылды;
- физикалық жүйелік принтер, PDF, PNG, JPEG/JPG, TIFF, BMP, WebP және SVG қолдау табады;
- A4, A3, пайдаланушы өлшемі және орам, кітаптық/альбомдық бағдар, жеке бет жиектері, 72–600 DPI және JPEG/WebP сапасы қолжетімді;
- растрлық файлдар терезе скриншоты ретінде емес, таңдалған DPI бойынша қағаздың нақты өлшемінде жасалады;
- алдын ала қарау, физикалық басып шығару, PDF, SVG және кескіндер ортақ page renderer пайдаланады;
- пішіндер үшін көлденең viewport сыртындағы барлық көрінетін баған басылып, экран ендері қалпына келтіріледі;
- бет, көпбетті ауқым және сапа баптаулары белсенді инженер профиліне жеке сақталады;
- ағымдағы, толық және пайдаланушы ауқымы, бір беттегі аралық, беттердің қабаттасуы, тақырыптарды қайталау, ауқым және бет нөмірлері қосылды;
- PDF пен физикалық принтер бір көпбетті құжат, ал растр/SVG форматтары нөмірленген бет файлдарын жасайды;
- қатаң Unicode preflight RU/KK/EN, инженерлік таңбалар, жоқ глифтер және қате қайта кодтауды тексереді; `QPrinter` үшін қаріп енгізу қосылған;
- жаңа тереңдік пішінінің бастапқы viewport мәні `50 м`, сақталған ауқым басым;
- пішіндер менеджеріне тікелей «Басып шығару / экспорт» батырмасы қосылды;
- өзгерістердің регрессиялық тексерулері: `93 passed`; толық assertions жинағы: `872 passed, 1 skipped`; Ruff қатесіз өтеді.

### English

- added one Print and Export Center for the active chart, tablet, and the form selected in Form Manager;
- supports the native physical printer, PDF, PNG, JPEG/JPG, TIFF, BMP, WebP, and SVG;
- provides A4, A3, custom and roll media, portrait/landscape orientation, independent margins, 72–600 DPI, and JPEG/WebP quality;
- raster files are generated at the real paper dimensions for the selected DPI rather than as window screenshots;
- preview, physical printing, PDF, SVG, and image export share one page renderer;
- forms include every visible column, including tracks outside the horizontal viewport, and restore screen widths afterward;
- page, pagination, and quality settings persist per active engineer profile;
- added current/full/custom range modes, units per page, overlap, repeated headers, page ranges, and page numbering;
- PDF and physical printing create one multi-page document, while raster/SVG outputs create numbered page files;
- strict Unicode preflight checks RU/KK/EN, engineering symbols, missing glyphs, and mojibake; font embedding is enabled for `QPrinter`;
- a new depth form starts with a `50 m` viewport while a saved range takes precedence;
- Form Manager now includes a direct Print / export button;
- changed-area regression checks: `93 passed`; full assertion set: `872 passed, 1 skipped`; Ruff passes without errors.

## Unreleased — adaptive A4 printing for Form Manager forms

### Русский

- в менеджер форм добавлен выбор `A4 — книжная` / `A4 — альбомная`;
- все видимые колонки, включая находящиеся за пределами горизонтальной прокрутки, попадают в печать;
- автоподбор балансирует ширины по типу дорожки, ограничивает чрезмерно широкие колонки и не обрезает форму;
- предварительный просмотр и PDF-экспорт используют один алгоритм и восстанавливают экранные ширины;
- настройка сохраняется отдельно для активного инженерного профиля;
- полный регрессионный прогон: `855 passed, 1 skipped`; Ruff проходит без ошибок.

### Қазақша

- пішіндер менеджеріне `A4 — кітаптық` / `A4 — альбомдық` таңдауы қосылды;
- көлденең айналдырудан тыс тұрғандарын қоса барлық көрінетін баған баспаға кіреді;
- автотаңдау жол түріне қарай ендерді теңестіреді, тым кең бағандарды шектейді және пішінді қимайды;
- алдын ала қарау мен PDF экспорты бір алгоритмді пайдаланып, экран ендерін қалпына келтіреді;
- баптау белсенді инженер профилі үшін бөлек сақталады;
- толық регрессиялық тексеру: `855 passed, 1 skipped`; Ruff қатесіз өтеді.

### English

- Form Manager now selects `A4 — portrait` or `A4 — landscape`;
- every visible column is printed, including columns outside the horizontal viewport;
- auto-fit balances widths by track type, caps extreme screen widths, and avoids horizontal clipping;
- print preview and PDF export share the same algorithm and restore screen widths afterward;
- the setting is persisted per active engineer profile;
- full regression suite: `855 passed, 1 skipped`; Ruff passes without errors.

## Unreleased — reliable visible depth/time interval control

### Русский

- поле «Интервал на экране» немедленно изменяет фактический вертикальный диапазон всех треков;
- добавлены готовые интервалы `1`, `5`, `10`, `20`, `30`, `40`, `50`, `60`, `70`, `80`, `90`, `100` и произвольное значение;
- ручной ввод применяется автоматически без Enter после завершения набора числа;
- модель планшета стала единственным источником состояния камеры, поэтому отображаемое значение больше не расходится с графиком;
- выбранный диапазон повторно фиксируется после изменения размера окна или перестроения формы;
- подпись показывает границы и фактический размер интервала; для временной оси используется её единица измерения;
- добавлены регрессионные тесты выбора, ручного ввода, синхронизации треков и resize.

### Қазақша

- «Экрандағы аралық» өрісі барлық тректің нақты тік ауқымын бірден өзгертеді;
- `1`, `5`, `10`, `20`, `30`, `40`, `50`, `60`, `70`, `80`, `90`, `100` дайын аралықтары және еркін мән қосылды;
- қолмен енгізілген сан Enter баспай-ақ теру аяқталғаннан кейін автоматты қолданылады;
- планшет моделі камера күйінің жалғыз көзі болды, сондықтан өрістегі мән мен график енді ажырамайды;
- терезе өлшемі немесе пішін өзгергеннен кейін таңдалған ауқым қайта бекітіледі;
- жазу шекаралар мен нақты аралық өлшемін көрсетеді, уақыт осі үшін оның өлшем бірлігі пайдаланылады;
- таңдау, қолмен енгізу, тректерді синхрондау және resize үшін регрессиялық тесттер қосылды.

### English

- the “Visible interval” control now changes the real vertical range of every track immediately;
- added presets `1`, `5`, `10`, `20`, `30`, `40`, `50`, `60`, `70`, `80`, `90`, `100`, plus custom values;
- manually typed values apply automatically without Enter after typing pauses;
- the tablet layout model is now the single source of camera state, preventing the control from diverging from the plots;
- the selected range is reasserted after window resize or form rebuild;
- the label shows both boundaries and the actual span, using the active time-axis unit when applicable;
- added regression tests for preset selection, typing, all-track synchronization, and resize.

## Unreleased — immediate RU / KK / EN interface switching

### Русский

- выбор языка применяется сразу, без перезапуска приложения;
- повторно переводятся меню, действия, вкладки, панели, LAS-таблица, браузер кривых, инспектор и навигация планшета;
- текущий проект, загруженные данные, форма планшета, масштаб и позиция прокрутки сохраняются;
- выбранный язык сохраняется в `QSettings` для следующего запуска;
- добавлен GUI-регрессионный тест последовательности `ru → kk → en`.

### Қазақша

- таңдалған тіл қолданбаны қайта іске қоспай бірден қолданылады;
- мәзірлер, әрекеттер, қойындылар, панельдер, LAS кестесі, қисықтар браузері, инспектор және планшет навигациясы қайта аударылады;
- ағымдағы жоба, жүктелген деректер, планшет пішіні, масштаб және айналдыру орны сақталады;
- таңдалған тіл келесі іске қосу үшін `QSettings` ішінде сақталады;
- `ru → kk → en` тізбегіне GUI-регрессиялық тест қосылды.

### English

- language selection now applies immediately without restarting the application;
- menus, actions, tabs, panels, the LAS table, curve browser, inspector, and tablet navigation are retranslated in place;
- the current project, loaded data, tablet form, zoom, and scroll position are preserved;
- the selected language remains stored in `QSettings` for the next launch;
- added GUI regression coverage for the `ru → kk → en` sequence.

## Unreleased — form range recovery and reliable depth navigation

### Русский

- менеджер форм больше не закрывается и не зависает из-за устаревших диапазонов `0 .. 0`, перепутанных границ или повреждённого пользовательского JSON;
- неподходящие диапазоны автоматически переводятся в автомасштаб, а повреждённый файл формы пропускается без удаления;
- выбранный глубинный масштаб и позиция прокрутки сохраняются при смене формы;
- колесо прокручивает общий интервал над графиком, заголовком и любой вложенной строкой параметра;
- ручной и предустановленный интервал сразу записывается в модель планшета и синхронно применяется ко всем колонкам.

### Қазақша

- ескі `0 .. 0` ауқымы, ауысқан шекаралар немесе зақымдалған пайдаланушы JSON файлы пішіндер менеджерін енді тоқтатпайды;
- жарамсыз ауқым автоматты масштабқа ауысады, ал зақымдалған пішін файлы жойылмай өткізіледі;
- пішінді ауыстырғанда таңдалған тереңдік масштабы мен айналдыру орны сақталады;
- тінтуір дөңгелегі графикте, тақырыпта және параметрдің кез келген ішкі жолында ортақ аралықты жылжытады;
- қолмен немесе тізімнен таңдалған аралық планшет моделіне бірден жазылып, барлық бағанға синхронды қолданылады.

### English

- the form manager no longer closes or stalls on legacy `0 .. 0` ranges, reversed bounds, or a damaged user-form JSON file;
- unusable ranges fall back to autoscale and damaged form files are skipped without being deleted;
- the selected depth span and scroll position are preserved when switching forms;
- the mouse wheel pans the shared range over plots, headers, and nested parameter rows;
- preset and manually entered spans are stored immediately in the tablet model and applied to every column.

## Unreleased — LAS text encoding and mojibake repair

### Русский

- добавлено распознавание UTF-8, Windows-1251, DOS CP866, KOI8-R, Mac Cyrillic и Latin-1 по читаемости заголовка LAS;
- исправляется типичное искажение CP866→Windows-1251 вида `‘Є®а®бвм`;
- `lasio` получает явно определённую кодировку вместо повторного независимого автоопределения;
- названия, описания, единицы, мнемоники и метаданные старых проектов очищаются перед отображением;
- добавлены регрессионные тесты для русского, казахского и английского текста.

### Қазақша

- LAS тақырыбының оқылымдылығы бойынша UTF-8, Windows-1251, DOS CP866, KOI8-R, Mac Cyrillic және Latin-1 кодтауларын анықтау қосылды;
- `‘Є®а®бвм` түріндегі CP866→Windows-1251 бұрмалануы автоматты түзетіледі;
- `lasio` қайтадан бөлек анықтамай, алдын ала табылған кодтауды пайдаланады;
- ескі жобалардағы атаулар, сипаттамалар, өлшемдер және мнемоникалар көрсету алдында қалпына келтіріледі;
- орыс, қазақ және ағылшын мәтініне регрессиялық тесттер қосылды.

### English

- added header-readability detection for UTF-8, Windows-1251, DOS CP866, KOI8-R, Mac Cyrillic, and Latin-1 LAS files;
- repairs the common CP866→Windows-1251 mojibake pattern such as `‘Є®а®бвм`;
- passes the detected encoding explicitly to `lasio` instead of running a second independent guess;
- normalizes names, descriptions, units, mnemonics, and legacy project metadata before display;
- added regression coverage for Russian, Kazakh, and English text.

## Unreleased — working LAS form rendering hotfix

### Русский

- исправлен `NameError: CurveStyle`, блокировавший построение базовой формы и кривых LAS;
- убран несовместимый ранний `clipToView` при создании `PlotDataItem` в pyqtgraph 0.14;
- добавлены GUI-регрессионные тесты реального построения заводской формы;
- исправлены типы редактора толщины линии и текста визира, Ruff/MyPy проходят без ошибок.

### Қазақша

- негізгі пішін мен LAS қисықтарын құруды тоқтатқан `NameError: CurveStyle` қатесі түзетілді;
- pyqtgraph 0.14 үшін `PlotDataItem` жасалған сәттегі үйлесімсіз `clipToView` алынды;
- зауыттық пішінді нақты көрсетуге арналған GUI-регрессиялық тесттер қосылды;
- сызық қалыңдығы редакторы мен визир мәтінінің типтері түзетілді, Ruff/MyPy қатесіз өтеді.

### English

- fixed the `NameError: CurveStyle` that prevented base forms and LAS curves from rendering;
- removed incompatible early `clipToView` construction under pyqtgraph 0.14;
- added GUI regression coverage for actual factory-form rendering;
- fixed line-width editor and cursor-text typing; Ruff and MyPy pass cleanly.

## Unreleased — working LAS base forms

### Русский

- базовая глубинная и временная формы автоматически заполняются реальными кривыми открытого LAS;
- кривые группируются по назначению и распределяются максимум по четыре на колонку;
- сохраняются исходные мнемоники, описания, единицы, цвета и рекомендуемые диапазоны;
- менеджер форм показывает доступные/отсутствующие параметры и совместимость оси;
- заводской рабочий шаблон открывается напрямую или сохраняется как редактируемая копия;
- редактор дорожки поддерживает надёжный выбор строки мышью и множественное добавление LAS-кривых.

### Қазақша

- негізгі тереңдік және уақыт пішіндері ашық LAS файлының нақты қисықтарымен автоматты толтырылады;
- қисықтар мақсаты бойынша топтастырылып, бір бағанға ең көбі төрттен орналастырылады;
- бастапқы мнемоника, сипаттама, өлшем бірлігі, түс және ұсынылған ауқым сақталады;
- пішіндер менеджері қолжетімді/табылмаған параметрлер мен ось сәйкестігін көрсетеді;
- зауыттық жұмыс үлгісі тікелей ашылады немесе өңделетін көшірме ретінде сақталады;
- жол редакторы тінтуірмен сенімді таңдауды және бірнеше LAS қисығын қосуды қолдайды.

### English

- basic depth and time forms are populated automatically from the open LAS dataset;
- curves are grouped by purpose and split into columns of at most four curves;
- exact source mnemonics, descriptions, units, colors, and recommended ranges are preserved;
- the form manager reports available/missing parameters and axis compatibility;
- a working factory template opens directly or can be saved as an editable copy;
- the track editor supports reliable mouse row selection and multi-select LAS-curve insertion.

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

### Tablet curves, scales, localization and cursor

- Added per-curve readable display names, linear/logarithmic scale and automatic/manual range.
- Added per-curve line color, width and style editing with persistence in tablet presets/forms.
- Multiple curves in one track now use stacked readable headers and independent normalized scales.
- Curve rows can be selected with a normal mouse click; curve headers support selection and context editing.
- Added synchronized cursor labels with depth/time and values in every visible curve track.
- Added fixed visible-depth presets (1, 5, 10, 20, 30, 40, 50 m) and custom span input.
- Completed RU/KK/EN strings for the new tablet and curve-settings controls.

## Unreleased

### Added

- Localized RU/KK/EN factory forms for Gas Ratio & Pixler depth interpretation and time monitoring.
- Factory forms for normalized-gas QC and detailed C1–C5 review.
- Stable factory identifiers and canonical bindings across all three interface languages.

## Unreleased

- Добавлены интервалы глубины 10–100 м и произвольный ввод с синхронным применением ко всем колонкам.
- Исправлена синхронизация поля масштаба с фактически видимым диапазоном.
- Улучшены многострочные заголовки кривых и читаемое название многопараметрической колонки.

## Unreleased — engineering form library, first slice

### Русский

- добавлены заводские формы d-экспоненты, технологии бурения, литологии и шламограммы, кальциметрии, ЛБА и комплексная геолого-технологическая форма;
- новые формы используют существующие специальные дорожки и канонические ParameterBinding;
- заводские формы защищены, а редактирование выполняется через сохраняемую пользовательскую копию;
- названия и структура локализованы на RU/KK/EN без изменения стабильных идентификаторов;
- обновлены план и статус следующего этапа Form Engine.

### Қазақша

- d-экспонента, бұрғылау технологиясы, литология және шламограмма, кальциметрия, ЛБА және кешенді геологиялық-технологиялық зауыттық пішіндер қосылды;
- жаңа пішіндер бар арнайы жолдарды және канондық ParameterBinding байланыстарын пайдаланады;
- зауыттық пішіндер қорғалған, өңдеу сақталатын пайдаланушы көшірмесі арқылы орындалады;
- атаулар мен құрылым тұрақты идентификаторларды өзгертпей RU/KK/EN тілдерінде локализацияланды;
- Form Engine келесі кезеңінің жоспары мен күйі жаңартылды.

### English

- added factory forms for D-exponent, drilling technology, lithology and cuttings, calcimetry, LBA, and an integrated geological-technological workflow;
- the new forms reuse the existing special track kinds and canonical ParameterBinding model;
- factory forms remain protected while editing is performed through a persistent user copy;
- names and structure are localized for RU/KK/EN without changing stable identifiers;
- updated the plan and status for the next Form Engine stage.

## Unreleased - reference Masterlog and visual LBA

### Русский

- добавлен заводской геолого-геохимический Masterlog со стратиграфией, бурением, глубиной,
  шламограммой, ЛБА, кальциметрией, литологией, компонентным газом и описанием пород;
- добавлена редактируемая шапка с литологической и ЛБА-легендой;
- ЛБА отображается цветными условными знаками: тип битумоида задаётся цветом, интенсивность 1-5 -
  формой и толщиной точки/кольца;
- поддерживаются коды ЛБ/МБ/МСБ/СБ/САБ и LB/LOB/MOB/HOB/VHO;
- добавлена временная заводская форма инженерно-технологического контроля;
- новые пресеты остаются защищёнными и используются как основа пользовательских копий.

### Қазақша

- стратиграфия, бұрғылау, тереңдік, шламограмма, ЛБА, кальциметрия, литология, компоненттік газ
  және жыныс сипаттамасы бар зауыттық геологиялық-геохимиялық Masterlog қосылды;
- литологиялық және ЛБА шартты белгілері бар өңделетін тақырып қосылды;
- ЛБА битумоид түрін түспен, ал 1-5 қарқындылығын нүкте/сақина пішінімен көрсетеді;
- ЛБ/МБ/МСБ/СБ/САБ және LB/LOB/MOB/HOB/VHO кодтары қолдау табады;
- инженерлік-технологиялық бақылаудың уақыттық зауыттық пішіні қосылды;
- жаңа үлгілер қорғалған және пайдаланушы көшірмелерінің негізі ретінде қолданылады.

### English

- added a factory geological-geochemical Masterlog with stratigraphy, drilling, depth, cuttings,
  LBA, calcimetry, lithology, component gas and rock descriptions;
- added an editable header with lithology and LBA legends;
- LBA now uses visual symbols: bitumen type is color-coded and intensity 1-5 is represented by
  point/ring geometry and weight;
- supports both ЛБ/МБ/МСБ/СБ/САБ and LB/LOB/MOB/HOB/VHO codes;
- added a factory time-based engineering-control form;
- the new presets remain protected and serve as bases for editable user copies.

## 0.6.0 — slice22

- Исправлен запуск графического редактора кривых: параметр теперь выбирается явно, режим доступен на главной панели и из контекстного меню планшета.
- Добавлены видимый курсор-карандаш, статус активного параметра и оранжевый предварительный штрих.
- Прямое редактирование расчётных кривых запрещено; после изменения исходной кривой зависимые параметры пересчитываются существующим контроллером зависимостей.
- Обновлены инструкции LAS Editor 2 на русском, казахском и английском языках.

<!-- BEGIN FORM_CONSTRUCTOR_SLICE23 -->
## Unreleased — constructor asset foundation (slice23)

- imported factory lithotype patterns with exact-file deduplication and preserved legacy semantic variants;
- imported normalized depth symbols with corrected display names and retained aliases;
- added constructor asset registry, depth-anchored placement model, previews and tests;
- added synchronized RU/KK/EN constructor plans.
<!-- END FORM_CONSTRUCTOR_SLICE23 -->

## 0.7.0 — 2026-07-21

### Universal Constructor

- Added the top-level **Constructor** menu and `Ctrl+Shift+K` shortcut.
- Integrated tablet Form Manager, Masterlog templates, WYSIWYG headers, columns, mapping,
  page profiles, preview and preflight in one workflow.
- Packaged 117 canonical lithotypes and 19 depth symbols with RU/KK/EN metadata,
  thumbnails, aliases and checksums.
- Added A0–A4, Letter, Legal, custom and roll profiles to page setup.
- Added physical page-boundary and overflow visualization to the header editor.
- Added BMP/JPEG/TIFF/WebP raster normalization in addition to PNG and SVG.
- Added image fit/fill/stretch, rotation and opacity.
- Added manual and used-plus-manual lithology legend scopes.
- Added semantic symbol X/Y offsets while preserving depth/interval/parameter/time anchors.
- Debounced Form Manager selection preview and rejected stale render revisions.
- Extended tablet wheel/touchpad depth navigation across plots, headers and empty areas.
