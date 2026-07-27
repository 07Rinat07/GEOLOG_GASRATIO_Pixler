# План проекта

Актуально на 27 июля 2026 года после среза 0.7.80. Здесь перечислена только незавершённая работа;
реализованные срезы находятся в [состоянии проекта](PROJECT_STATUS.md), корневой
[истории изменений](CHANGELOG.md) и release notes.

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
- [x] embedded Data и безопасный relative FileUri без сетевого ETP;
- [x] time/depth index, Well/Wellbore metadata и UOM conversion;
- [x] Semantic Channel Dictionary Import Review;
- [x] атомарное создание и регистрация immutable Dataset;
- [x] синтетический fixture и regression tests.

## Завершено в 0.7.80: WITSML 1.4.1.1 SOAP read-only

- [x] GetVersion/GetCap и read-only Well → Wellbore → Log → LogCurveInfo → LogData;
- [x] timeout, bounded retry, response-size guard и hash-chained audit;
- [x] credentials вне project file через Windows Credential Manager;
- [x] повторное использование Import Review и атомарной регистрации Dataset;
- [x] запрет Add/Update/Delete на уровне клиента.

## Следующий продуктовый этап: WITSML 2.1 / ETP 1.2

- [ ] выбрать и проверить ETP 1.2 client library;
- [ ] реализовать session negotiation, Discovery и Channel Streaming;
- [ ] преобразовать ChannelData в общий normalized measurement pipeline;
- [ ] добавить reconnect и восстановление подписок без потери provenance.

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
