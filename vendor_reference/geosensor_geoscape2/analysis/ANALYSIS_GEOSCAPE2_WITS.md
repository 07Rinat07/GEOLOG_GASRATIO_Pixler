# Статический анализ GeoScape 2: WITS/WITSML-материалы

Дата анализа: 2026-07-27T08:37:52.927885+00:00

## Границы анализа

Архив исследован статически. Исполняемые файлы и DLL/BPL не запускались. Проверены структура ZIP, хеши, PE-заголовки, импортируемые библиотеки, встроенные строки, имена классов/форм/таблиц и поставляемые справочники.

## Состав архива

- Файлов и каталогов: 367.
- Распакованный объём: 243,432,793 байт.
- Сжатый объём элементов: 162,786,847 байт.
- SHA-256 исходного ZIP: `b9b358b76e1956058421ce6969ff04a0c961a986160dc2f207d2bfa5a921cf44`.
- Path traversal и дублирующиеся пути не обнаружены.

## Наиболее ценные материалы

### `GeoScape/WITS.csv`

Это полный машинно-читаемый словарь WITS Level 0:

- 963 полей;
- записи 1–25;
- колонки `ID`, `Index`, `Description`, `ShortMnemonic`, `LongMnemonic`, `Type`, `Length`;
- типы: {'A': 112, 'S': 125, 'L': 81, 'D': 28, 'T': 27, 'F': 590}.

| Record | Fields |
|---:|---:|
| 1 | 45 |
| 2 | 36 |
| 3 | 26 |
| 4 | 39 |
| 5 | 23 |
| 6 | 34 |
| 7 | 26 |
| 8 | 55 |
| 9 | 29 |
| 10 | 33 |
| 11 | 35 |
| 12 | 28 |
| 13 | 48 |
| 14 | 29 |
| 15 | 59 |
| 16 | 41 |
| 17 | 38 |
| 18 | 31 |
| 19 | 31 |
| 20 | 65 |
| 21 | 49 |
| 22 | 10 |
| 23 | 37 |
| 24 | 64 |
| 25 | 52 |

Критически важная стандартная шапка каждой записи:

| Item | Назначение |
|---:|---|
| 01 | Well Identifier |
| 02 | Sidetrack/Hole Sect No. |
| 03 | Record Identifier |
| 04 | Sequence Identifier |
| 05 | Date |
| 06 | Time |
| 07 | Activity Code |

Это означает, что последовательность GSWITS находится в item `04`, а не в item `02`.

### `GeoScape/LocalAppDataFolder/GeoSensor/GSWITS.mdb`

По структурам и встроенным запросам обнаружены:

- таблицы/наборы `WITS`, `WITSRecordStreamMap`, `WITSActivity`, `WITSMeasureSystem`, `NetConnectionLog`;
- `RecordID`, `FieldID`, `GID`, `WITSUnit`, `MathType`, `IsAdditional`, `CheckToNewData`;
- коэффициенты `ToMetricAngular`, `ToMetricOffset`, `OwnAngularCoef`, `OwnOffsetCoef`;
- настройки `WITSRecordIsSend`, `WITSRecordSentInterval`;
- привязка GeoScape GID к WITS record/item;
- отдельная логика дополнительных полей и версий GeoScape.

База является главным источником фактических vendor-mapping и единиц. Для полного извлечения таблиц потребуется Access/Jet OLEDB на Windows либо `mdbtools`.

### `GeoScape/GSWITSProxy.exe`

Статические признаки:

- PE32, x86, Windows GUI;
- timestamp PE: 2025-09-18;
- Delphi/VCL/Indy-компоненты;
- `TIdTCPClient`, `TIdTCPServer`, `IdRawClient`, ICMP ping;
- TCP client/server режимы, host/port tests и connection-state timers;
- формы настройки сети, записи WITS, activity code, дополнительных полей;
- журнал сетевых соединений и последних отправленных записей;
- ADO/Jet подключение к `GSWITS.mdb`;
- record interval, current sequence, last sent date;
- отдельный канал связи с GeoScape и отдельный WITS TCP/COM канал.

### `GeoScape/GSWITSReceiver.bpl`

Это более прямой эталон для нашего приёмника:

- загружает `WITS.csv`;
- классы `TWITS0`, `TWITS0Stream`, `TWITS0ThreadedStringList`, `TWITS0FileStream`;
- `TWITS0_TCP_COMReceiver`;
- режимы `wctTCPClient` и `wctTCPServer`;
- поддержка COM/serial;
- настраиваемая кодировка;
- sequence state, local/remote time;
- mapping `record/item → GID`;
- коэффициенты преобразования и окно выбора принимаемых полей;
- диагностики invalid record/item/date/sequence.

### WITSML-материалы

- `GSWITSMLServer.exe`;
- `GSWITSML.mdb` с профилями, mnemonics, UOM, offset/multiplier и log time/depth classes;
- `WITSMLCodes.csv` с кодами WITSML 1.4;
- `capServers 1.3.1.1.xml` и `capServers 1.4.1.1.xml`;
- `WITSMLCodes.csv` в двух расположениях.

Они полезны для этапов G/H и interoperability matrix, но не являются доказательством поведения конкретного удалённого WITSML Store.

## Критическое расхождение с проектом 0.7.82

> Статус исправления: устранено в compatibility patch 0.7.83. Sequence теперь читается из item `04`, а стандартная шапка и полный vendor catalog покрыты regression tests.


В текущем `wits0_parser.py` стандартная шапка определена неверно:

- item 01 ошибочно интерпретируется как record identifier;
- item 02 — как sequence;
- item 03 — как well identifier;
- item 04 — как wellbore identifier.

Vendor-словарь показывает правильную схему `01 Well`, `02 Sidetrack`, `03 Record`, `04 Sequence`. Поэтому default `sequence_item_no` должен быть изменён с `2` на `4`, а тестовые кадры — приведены к реальному формату GSWITS.

## Что переносить в проект

1. Производный JSON/CSV-словарь WITS 1–25 с provenance и SHA-256.
2. Исправленную стандартную шапку и sequence tracking по item 04.
3. Тестовые кадры из руководства и синтетические кадры на основе `WITS.csv`.
4. Архитектурные признаки receiver: TCP client/server, bounded buffer, selectable fields, encoding, unit coefficients, reconnect и connection journal.
5. Отдельный vendor-profile overlay; встроенный профиль не должен зависеть от установленной Access DB.

## Что не переносить

- бинарный код EXE/BPL/DLL;
- формы и ресурсы GeoScape;
- закрытые таблицы целиком без необходимости;
- логины/пароли и локальные пути разработчиков;
- write-операции WITSML.

## Следующая техническая правка

До продолжения ETP I.2 необходимо выпустить compatibility patch для WITS0: исправить header items и sequence item, добавить полный vendor dictionary и regression tests. Иначе текущая sequence-диагностика для реального GSWITS будет давать ложные результаты.
