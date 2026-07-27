# Каталог совместимости GeoSensor WITS Level 0

## Назначение

Встроенный каталог `geosensor-wits-level0.json` создан из машинно-читаемого файла
`GeoScape/WITS.csv`, поставленного в архиве GeoScape 2. Он содержит 963 пары `record/item` для
записей 1–25, описание, short/long mnemonic, объявленный тип и длину.

Каталог дополняет профиль GSWITS. Профиль задаёт проверенные единицы, aggregation, index type и
политику отправки для поддерживаемых записей, а каталог позволяет parser распознавать остальные
стандартные поля без ложной диагностики `unknown record/item`.

## Стандартная шапка

- `01` — Well Identifier;
- `02` — Sidetrack/Hole Section Number;
- `03` — Record Identifier;
- `04` — Sequence Identifier;
- `05` — Date;
- `06` — Time;
- `07` — Activity Code.

Номер последовательности извлекается только из item `04`.

## Воспроизводимость и границы

Каталог пересобирается командой `tools/build_geosensor_wits_catalog.py`. Инструмент проверяет ZIP
paths, читает только `GeoScape/WITS.csv` и не запускает vendor binaries. Исходные EXE, BPL, MDB,
FDB и PDF не входят в wheel или исходный архив. Хеши и результаты анализа находятся в
[reference_manifest.json](../../vendor_reference/geosensor_geoscape2/inventory/reference_manifest.json)
и [ANALYSIS_GEOSCAPE2_WITS.md](../../vendor_reference/geosensor_geoscape2/analysis/ANALYSIS_GEOSCAPE2_WITS.md).
