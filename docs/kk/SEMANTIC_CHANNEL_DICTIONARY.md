# Semantic Channel Dictionary

## Мақсаты

Сөздік LAS, CSV/TXT/Excel және GeoScape/Paradox арналарына ортақ инженерлік мағына береді.
Ол бастапқы атауды жасырын өзгертпейді және белгісіз өлшем бірлігін болжауға тырыспайды.
Сәйкестендіру нәтижесі каталог жаңарғаннан кейін де жоба мағынасы өзгермеуі үшін curve ішінде
сақталады.

## Ереже көздері

- Sensors catalog — canonical mnemonic, vendor aliases, legacy `S/GID`, sensor ID, family,
  category және reference UOM;
- `UomDictionary` — анық UOM aliases және quantity class;
- `SemanticChannelDictionary` — белгілерді тұрақты definition және binding-ке біріктіреді.

Vendor aliases үшін Sensors catalog жалғыз дереккөз болып қалады.

## Curve binding

`SemanticChannelBinding` мыналарды сақтайды:

- canonical kind және canonical mnemonic;
- quantity class;
- canonical UOM және бастапқы source UOM;
- aliases, sensor ID, source, family және category;
- нақты source mnemonic;
- confidence, matched-by және evidence.

Project format v16 binding-ті curve metadata ішінде сақтайды. Legacy project ашылғанда binding
қайта құрылады, бірақ бұрын сақталған canonical mnemonic ауыстырылмайды.

## UOM саясаты

Тек белгілі aliases нормалданады. Әр UOM length, time, pressure, volume fraction, flow rate,
density, temperature сияқты quantity class-қа жатады. Белгісіз мән `unknown` болып қалады;
жасырын conversion немесе болжам жоқ. Channel мағынасы мен source UOM физикалық түрі сәйкес
келмесе, confidence төмендейді және Import Review `channel-uom-conflict` қатесін береді.

## Интеграция және Import Review

Binding CSV/Excel, LAS және Paradox import кезінде жасалады және copy, transfer, merge,
reverse/resample, TIME↔DEPTH, aggregation және dataset JSON export кезінде сақталады.

`build_import_review(dataset)` index, semantic binding, valid/NULL саны, unresolved channel,
missing/unknown UOM, quantity conflict, all-null және duplicate canonical kind туралы read-only
нәтиже береді. Ол dataset-ті өзгертпейді. Интерактивті терезе, manual overrides және атомарлық
растау — келесі вертикальды кезең.
