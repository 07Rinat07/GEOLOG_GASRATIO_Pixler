# Changelog

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
