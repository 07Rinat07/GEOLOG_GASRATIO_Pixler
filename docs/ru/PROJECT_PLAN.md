# План проекта

## Завершено в 0.7.81: WITSML 2.1 / ETP 1.2

- [x] защищённая WebSocket-сессия и protocol negotiation;
- [x] read-only Discovery, Store, Data Array и channel subscription;
- [x] correlation, multipart FIN, ACK и bounded reconnect;
- [x] secrets вне проекта и hash-chained audit.

## Следующий ETP-срез

- [ ] interoperability matrix с реальными ETP servers;
- [ ] ChannelData → normalized batches → append-only ETP AcquisitionSession;
- [ ] semantic/UOM mapping и workspace persistence;
- [ ] reconnect overlap и soak 8–24 часа.

Актуально на 27 июля 2026 года после среза 0.7.81. Здесь перечислена только незавершённая работа;
реализованные срезы находятся в [состоянии проекта](PROJECT_STATUS.md), корневой
[истории изменений](../CHANGELOG.md) и release notes.

## Приоритет: полевая приёмка WITS0

Raw capture, parser, Import Review, normalized batches, append-only `AcquisitionSession`, live
monitor и программный reliability-контур готовы. До полевой готовности остаётся:

- [ ] получить 5–10 минут реального обезличенного GSWITS raw-потока;
- [ ] подтвердить TCP mode, IP, порт, кодировку, header fields и интервалы records;
- [ ] сверить встроенный GeoScape profile и custom profile с реальными record/item;
- [ ] выполнить 8–24-часовой Windows soak-test с реальным GSWITS и сохранить JSON-отчёт;
- [ ] проверить reconnect после перезапуска GSWITS, приложения и Windows;
- [ ] провести контролируемый low-space/disk-full тест без потери raw;
- [ ] определить Windows startup/service strategy и подписанный field checklist;
- [ ] добавить независимые дорожки/шкалы для несовместимых единиц;
- [ ] определить политику новой source session после закрытия предыдущей.

## Завершено в 0.7.79: WITSML offline data import

- [x] выбор `ChannelSet`, активного `Index` и scalar numeric `Channel`;
- [x] чтение embedded Data и безопасного relative FileUri без сетевого ETP;
- [x] time/depth index и Well/Wellbore metadata binding;
- [x] Semantic Channel Dictionary/UOM Import Review с численным conversion;
- [x] атомарное создание и регистрация immutable Dataset;
- [x] синтетический fixture с явным provenance и regression tests.

## Следующий продуктовый этап: WITSML 1.4.1.1 SOAP read-only

- [ ] реализовать GetVersion/GetCap и read-only Well → Wellbore → Log → LogData;
- [ ] хранить credentials вне project file;
- [ ] добавить timeout/retry/audit без Add/Update/Delete.

## Приёмка GeoScape II GS2

- [ ] добавить версионные проекции и обезличенные Access/Paradox fixtures других версий GeoScape;
- [ ] проверить повреждённые, обрезанные и многочастные таблицы на golden fixtures;
- [ ] сверить СГ-8 и минимум два других GS2 с эталонным экспортом GeoScape в LAS/Excel;
- [ ] подтвердить C1–C5, суммарный газ, TIME/DEPTH, единицы и разбиение файлов;
- [ ] проверить Gas Ratio/Pixler на каналах, доказанно сопоставленных через `GS2.mdb`.

## Release recovery

- [ ] устранить текущие ошибки и internal error mypy;
- [ ] выполнить подписанный tablet/annotation/PDF/HiDPI/physical-printer smoke checklist;
- [ ] публиковать stable build только после зелёного обязательного gate.

## Критерий ближайшей приёмки

Один реальный GSWITS stream должен пережить reconnect, паузу представления, сохранение проекта,
аварийный restart и low-space boundary. Raw bytes, connection journal, recovery manifest,
`AcquisitionSession`, checkpoints и Dataset projection должны оставаться согласованными.
