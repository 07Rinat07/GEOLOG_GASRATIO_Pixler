# Mouse-driven interpretation interval editing

## Русский

На панели и в меню «Планшет» доступны три взаимоисключающих режима:

- **Выбор** (`Alt+1`) — hit-testing и открытие свойств существующего интервала;
- **Рисование** (`Alt+2`) — протягивание от кровли до подошвы на дорожке интерпретации;
- **Границы** (`Alt+3`) — перетаскивание верхней или нижней границы существующего интервала.

Глубины привязываются к ближайшим конечным отсчётам активного dataset. Во время жеста
показывается пунктирный полупрозрачный preview. `Esc` отменяет незавершённую операцию. После
отпускания мыши команда проходит через `InterpretationController`: проверяется диапазон dataset,
порядок кровли/подошвы и пересечение с интервалами того же типа. Только успешно проверенная
команда сохраняется в проекте и истории Undo/Redo (`Ctrl+Alt+Z` / `Ctrl+Alt+Shift+Z`).

Если в скважине ещё нет интерпретации, при включении режима рисования создаётся «Основная
интерпретация» и добавляется дорожка интервалов. Новый интервал получает тип выбранной полосы,
автоматическую подпись и цвет; точные свойства затем редактируются в правой панели.

## Қазақша

«Планшет» мәзірі мен құралдар тақтасында үш режим бар: **Таңдау** (`Alt+1`), **Сызу**
(`Alt+2`) және **Шекаралар** (`Alt+3`). Тереңдік белсенді dataset-тің ең жақын нақты
өлшеміне байланады, әрекет кезінде жартылай мөлдір preview көрсетіледі, ал `Esc` әрекетті
болдырмайды. Тышқан жіберілгеннен кейін диапазон, төбе/табан реті және бір түрдегі аралықтардың
қиылыспауы тексеріледі. Сәтті команда ғана жобаға және Undo/Redo тарихына жазылады.

## English

The Tablet menu and toolbar expose three exclusive modes: **Select** (`Alt+1`), **Draw**
(`Alt+2`), and **Boundaries** (`Alt+3`). Depths snap to the nearest finite sample in the active
dataset. A translucent dashed preview is shown during the gesture, and `Esc` cancels it. On mouse
release the existing `InterpretationController` validates dataset bounds, top/bottom ordering, and
same-type overlap. Only a valid command is persisted and recorded in Undo/Redo history
(`Ctrl+Alt+Z` / `Ctrl+Alt+Shift+Z`).
## Литологические интервалы / Литологиялық аралықтар / Lithology intervals

**RU.** На дорожке «Литология» удерживайте `Shift`, нажмите левую кнопку и протяните от кровли до подошвы. После отпускания откроется отдельное окно: можно уточнить обе глубины и выбрать ровно одну породу. Состав шламовой пробы, ЛБА, кальциметрия и текстовое описание редактируются в редакторе пробы и не смешиваются с литологическим интервалом.

**KK.** «Литология» жолағында `Shift` ұстап, сол жақ батырмамен төбеден табанға дейін созыңыз. Батырманы жібергенде екі тереңдікті түзетуге және бір тау жынысын таңдауға арналған терезе ашылады. Шлам құрамы, ЛБА, кальциметрия және мәтіндік сипаттама үлгі редакторында бөлек өңделеді.

**EN.** Hold `Shift` and left-drag from top to bottom in a Lithology track. On release, a dedicated dialog lets the user correct both depths and select exactly one rock type. Cuttings composition, LBA, calcimetry, and rich descriptions remain separate sample-editor responsibilities.

