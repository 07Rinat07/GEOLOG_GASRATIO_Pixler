# GeoSensor GeoScape 2 — внешние материалы совместимости

Этот каталог содержит только производные фактические данные, хеши и результаты статического анализа,
необходимые для совместимости GEOLOG GASRATIO@Pixler с GSWITS/WITSML.

## Источник

- исходный архив: `GeoScape2.zip`;
- поставщик: GeoSensor;
- SHA-256 архива указан в `inventory/reference_manifest.json`;
- руководство GSWITS идентифицируется отдельным SHA-256 в том же manifest.

Оригинальные EXE, BPL, DLL, MDB, FDB и PDF **не включаются** в исходный архив проекта и wheel.
Они остаются внешними reference-материалами пользователя. Исполняемые файлы не запускались.

## Что включено

- `analysis/ANALYSIS_GEOSCAPE2_WITS.md` — границы и результаты статического анализа;
- `inventory/reference_manifest.json` — хеши исходного архива, руководства и ключевых файлов;
- `inventory/static_analysis_inventory.json` — расширенный inventory исходного архива;
- `derived/wits_level0_fields.json` — полный производный словарь 963 WITS Level 0 fields;
- `derived/wits_level0_fields.csv` — тот же словарь в табличном виде;
- `derived/wits_level0_summary.json` — counts, record inventory и стандартная шапка;
- `derived/witsml1411_result_codes.json` — нормализованные result/error codes;
- `derived/witsml_capabilities_summary.json` — read-only summary capServer 1.3.1.1/1.4.1.1.

Runtime-копия каталога для parser находится в:

```text
src/geoworkbench/resources/wits/catalogs/geosensor-wits-level0.json
```

## Критический контракт GSWITS

```text
01 Well Identifier
02 Sidetrack/Hole Sect No.
03 Record Identifier
04 Sequence Identifier
05 Date
06 Time
07 Activity Code
```

Следовательно, source sequence читается из item `04`.

## Воспроизводимая генерация

```powershell
python tools/build_geosensor_wits_catalog.py `
  C:\path\to\GeoScape2.zip `
  vendor_reference\geosensor_geoscape2\derived
```

Инструмент читает только `GeoScape/WITS.csv`, проверяет ZIP paths и не запускает vendor binaries.

Для полного read-only экспорта mapping из `GSWITS.mdb` на Windows используется
`tools/export_geosensor_gswits_mdb.ps1`. Скрипт работает через ACE/Jet OLE DB, не выполняет
INSERT/UPDATE/DELETE и пишет CSV плюс hash manifest.

## Лицензионная граница

Проект использует только публично наблюдаемые форматы, названия полей, конфигурационные признаки и
производные справочники. Код и ресурсы GeoScape не копируются и не связываются с приложением.
