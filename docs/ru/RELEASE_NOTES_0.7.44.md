# 0.7.44 — версионированная lag/depth correction

Тестовая сборка. Project format повышен до v19; lag correction schema v1.

## Русский

- добавлены immutable профили и непрерывные revisions для gas, cuttings и generic каналов;
- поддерживаются constant-time, annular-volume/flow, pump-strokes и manual control points;
- каждая revision создаёт отдельный derived dataset с source и corrected DEPTH indexes;
- acquisition dataset и append-only journal не изменяются и не переписываются;
- source prefix и output подписываются SHA-256; divergence/tampering блокируют загрузку;
- revision хранит формулу, параметры, индексы, кривые, автора, UTC timestamp и acquisition provenance;
- можно активировать прежнюю revision без удаления последующих результатов;
- добавлено RU/KK/EN окно «Расчёты → Коррекция lag/depth...» с preview и выбором оси;
- миграция `v18 → v19` добавляет пустой `lag_correction_profiles` без изменения проекта.

## Қазақша

- gas, cuttings және generic каналдары үшін immutable профильдер мен үздіксіз revisions қосылды;
- constant-time, annular-volume/flow, pump-strokes және manual control points әдістері бар;
- әр revision source және corrected DEPTH indexes бар бөлек derived dataset жасайды;
- acquisition dataset пен append-only journal өзгермейді;
- source prefix және output SHA-256 арқылы тексеріледі, divergence/tampering жүктеуді тоқтатады;
- бұрынғы revision-ды кейінгі нәтижелерді жоймай белсендіруге болады;
- RU/KK/EN интерфейсінде preview және ось таңдау терезесі қосылды;
- `v18 → v19` migration жоба деректерін өзгертпей бос profile collection жасайды.

## English

- added immutable profiles and contiguous revisions for gas, cuttings, and generic channels;
- added constant-time, annular-volume/flow, pump-stroke, and manual control-point methods;
- each revision materializes a separate derived dataset with source and corrected depth indexes;
- the acquisition dataset and append-only journal are never rewritten;
- source-prefix and output SHA-256 fingerprints reject divergence and tampering;
- revisions preserve formula, parameters, indexes, curve IDs, author, UTC timestamp, and acquisition provenance;
- any saved revision can be reactivated without deleting later materialized results;
- added a localized Calculations-menu dialog with preview and explicit axis selection;
- migration `v18 → v19` adds an empty profile collection without changing existing data.

## Проверка

- focused: 72 passed;
- available headless regression: 987 passed, 4 skipped, 3 deselected;
- full Qt/LAS/Ruff/mypy and Windows smoke gates remain pending in this container.
