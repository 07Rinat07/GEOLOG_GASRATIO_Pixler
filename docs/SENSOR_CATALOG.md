# Sensors and mnemonic catalog / Справочник Sensors и мнемоник / Sensors және мнемоникалар анықтамалығы

## Русский

Проект содержит нормализованный справочник `src/geoworkbench/resources/sensors.ru.json`,
сформированный из предоставленных таблиц `Editor/Sensors.DB`, `Geolog-055/Sensors.DB` и
проверенных LAS-псевдонимов. Исходные бинарные таблицы не требуются для запуска приложения.
Аудит архива GeoScape2 подтвердил покрытие всех 317 уникальных `GID` из его `Sensors.DB`, в том
числе `1626=iC4`, `1627=iC5`, `1628=nC4` и `1629=nC5`.
Руководство GeoScape II дополнительно подтверждает семикомпонентный выход хроматографа. Поэтому
старые `C4/C5` рядом с `iC4/iC5` используются как контекстные алиасы `nC4/nC5`, но явные
суммарные каналы и численно одинаковые дубли автоматически не переосмысливаются. Канонический
набор `C1/C2/C3/nC4/iC4/nC5/iC5` дополнительно сверён с официальной терминологией SLB.

Каждая запись хранит стабильный ID, каноническую мнемонику, список псевдонимов, русское
название, единицу измерения, категорию, физически совместимое семейство дорожки,
рекомендуемый диапазон, цвет и происхождение записи. Сопоставление учитывает регистр,
разделители и смешение похожих кириллических/латинских букв, например `С1` и `C1`.

После загрузки LAS панель «Кривые LAS» показывает исходную и каноническую мнемоники,
фактический диапазон данных и диапазон справочника. Команда «Правка → Справочник Sensors и
мнемоник...» открывает полный поиск по справочнику. Внешний JSON можно подключить на текущий
сеанс; файл должен использовать схему версии 1 с разделами `sensors` и, при необходимости,
`legacy_fields`. Перед применением проверяются ID, категории, семейства, цвета и диапазоны.

Справочник помогает распознавать и группировать каналы, но не изменяет исходные имена кривых в
LAS и не подменяет фактические единицы или значения данных.

## Қазақша

Жобада `Editor/Sensors.DB`, `Geolog-055/Sensors.DB` кестелері және тексерілген LAS бүркеншік
аттары негізінде жасалған `src/geoworkbench/resources/sensors.ru.json` қалыптандырылған
анықтамалығы бар. Бағдарламаны іске қосу үшін бастапқы бинарлық кестелер қажет емес.
GeoScape2 мұрағатын тексеру оның `Sensors.DB` кестесіндегі барлық 317 бірегей `GID`, соның ішінде
`1626=iC4`, `1627=iC5`, `1628=nC4` және `1629=nC5` қамтылғанын растады.
GeoScape II нұсқаулығы хроматографтың жеті компоненттік шығысын да растайды. Сондықтан ескі
`C4/C5` арналары `iC4/iC5` жанында `nC4/nC5` контекстік алиастары ретінде қолданылады, бірақ
нақты жиынтық арналар мен сандық бірдей көшірмелер автоматты түрде қайта түсіндірілмейді.
`C1/C2/C3/nC4/iC4/nC5/iC5` канондық жиыны SLB ресми терминологиясымен де салыстырылды.

Әр жазба тұрақты ID, канондық мнемоника, бүркеншік аттар, орысша атау, өлшем бірлігі, санат,
физикалық тұрғыдан үйлесімді жолақ тобы, ұсынылатын диапазон, түс және дереккөзді сақтайды.
Сәйкестендіру регистрді, бөлгіштерді және `С1`/`C1` сияқты ұқсас кирилл/латын таңбаларын
ескереді.

LAS жүктелгеннен кейін «LAS қисықтары» панелі бастапқы және канондық мнемоникаларды, нақты
деректер диапазонын және анықтамалық диапазонын көрсетеді. «Өңдеу → Sensors және мнемоникалар
анықтамалығы...» толық іздеуді ашады. 1-нұсқа схемасындағы сыртқы JSON ағымдағы сеансқа
қосылады; ID, санат, жолақ тобы, түс және диапазондар алдын ала тексеріледі.

Анықтамалық арналарды тануға және топтастыруға көмектеседі, бірақ бастапқы LAS атауларын,
өлшем бірліктерін немесе мәндерін өзгертпейді.

## English

The project ships a normalized `src/geoworkbench/resources/sensors.ru.json` catalog derived from
the supplied `Editor/Sensors.DB`, `Geolog-055/Sensors.DB`, and validated LAS aliases. The original
binary tables are not required at runtime.
An audit of the GeoScape2 archive confirmed coverage of all 317 unique `GID` values from its
`Sensors.DB`, including `1626=iC4`, `1627=iC5`, `1628=nC4`, and `1629=nC5`.
The GeoScape II manual also confirms a seven-component chromatograph output. Legacy `C4/C5`
beside `iC4/iC5` are therefore contextual aliases for `nC4/nC5`; explicitly total channels and
numerically identical copies are not reinterpreted automatically. The canonical
`C1/C2/C3/nC4/iC4/nC5/iC5` set was also checked against official SLB terminology.

Each entry stores a stable ID, canonical mnemonic, aliases, Russian name, unit, category,
physically compatible track family, recommended range, color, and provenance. Matching is
case-insensitive, separator-tolerant, and handles common Cyrillic/Latin homoglyphs such as `С1`
and `C1`.

After LAS import, the “LAS curves” panel displays original and canonical mnemonics, the actual data
range, and the reference range. “Edit → Sensors and mnemonic reference...” opens the complete
searchable catalog. An external schema-version-1 JSON can be connected for the current session;
IDs, categories, families, colors, and ranges are validated before activation.

The catalog recognizes and groups channels without renaming source LAS curves or replacing their
actual units and values.

## User mnemonic rules

`UserMnemonicRegistry` stores user mappings in `QSettings` under schema `user_rules_v1`. A rule maps one foreign mnemonic and optional aliases to a canonical parameter definition. User definitions are merged before the built-in Sensors catalog and therefore win deterministic alias matching. The UI supports create, edit, delete, JSON import, and JSON export. These mappings affect curve classification and automatic tablet-track construction for every later import without modifying source LAS data.
