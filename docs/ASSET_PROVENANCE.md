# Provenance и лицензии встроенных lithology/symbol assets

Документ описывает проверяемый контракт `SEC-05` для ресурсов, которые поставляются внутри
пакета `geoworkbench` из `resources/constructor_assets`.

## Текущий результат review

В проекте реально поставляются две коллекции constructor assets:

- `constructor_assets/lithology` — исходные BMP, thumbnails/transparent PNG и собственный
  `manifest.json`; manifest называет исходные архивы `Litol_Bmp(2).zip` и `Litol2_Bmp(2).zip`;
- `constructor_assets/symbols` — исходные BMP, thumbnails/transparent PNG и собственный
  `manifest.json`; manifest называет исходный архив `Значки(2).zip`.

Существующие manifests фиксируют source filenames, SHA-256 и производные файлы, но в репозитории
не найдено archive-specific доказательство происхождения, правообладателя или разрешения на
распространение этих трёх архивов. Root `LICENSE` объявляет assets проекта proprietary, однако
это общее заявление само по себе не используется как доказательство прав на импортированный
архив неизвестного происхождения.

Поэтому обе коллекции имеют `review_status = unresolved` в
`src/geoworkbench/resources/asset-provenance.json`. Это намеренное fail-closed состояние, а не
предположение о нарушении лицензии.

## Машиночитаемый контракт

Команда coverage gate:

```powershell
python tools/check_asset_provenance.py
```

Она завершается успешно только когда:

- каждый каталог `constructor_assets/*` имеет собственный `manifest.json`;
- каждый обнаруженный `constructor_assets/*/manifest.json` покрыт ровно одной provenance записью;
- нет loose-файлов непосредственно в корне `constructor_assets` вне коллекции;
- schema, `kind` и `source_archives` provenance записи совпадают с существующим asset manifest;
- source archive lists состоят только из уникальных непустых строк;
- asset IDs в каждом manifest уникальны, а asset-level `source_archives` являются подмножеством
  archive list своей коллекции;
- все `asset_path` и `thumbnail_path`, перечисленные в manifests, остаются внутри каталога именно
  своей коллекции, существуют и не дублируются между разными asset records одного типа пути;
- development tree `resources/constructor_assets` и реально пакуемый tree
  `src/geoworkbench/resources/constructor_assets` имеют одинаковый набор файлов и совпадают
  побайтово по SHA-256;
- нет неизвестного `review_status`;
- запись со статусом `cleared` содержит непустые строковые `rights_holder`, `license_basis` и
  `evidence_reference`.

Список коллекций не захардкожен в validator: он строится из фактически пакуемых manifests.
Поэтому добавление новой папки с `manifest.json` без provenance записи, появление каталога без
manifest или drift только одной из двух копий assets делает gate красным. Подмена provenance
полями другого типа, path traversal или ссылка lithology manifest на shipped symbol file также
не могут использоваться для получения зелёного coverage gate.

`asset-provenance.json` находится на верхнем уровне `src/geoworkbench/resources`, который уже
включён в package-data шаблоном `resources/*.json`; regression test фиксирует этот packaging
contract.

Release workflow запускает coverage gate в Windows security job. Изменение source archive,
структуры shipped collections или development/package parity без синхронного provenance update
должно сделать CI красным.

## Строгая проверка clearance

Перед юридически подтверждённым распространением встроенных коллекций используется:

```powershell
python tools/check_asset_provenance.py --require-cleared
```

Пока хотя бы одна коллекция имеет `review_status = unresolved`, команда обязана завершаться
ненулевым кодом. Нельзя менять статус на `cleared` только для получения зелёного gate.

Допустимое основание для `cleared` должно быть проверяемым и относиться именно к коллекции:
письменное разрешение правообладателя, подтверждённое собственное авторство исходников,
лицензия источника с разрешением требуемого распространения или замена коллекции на ресурсы с
однозначным provenance. Ссылка/документ основания записывается в `evidence_reference`.

## Критерий закрытия SEC-05

`SEC-05` можно отметить `[x]` в `PROJECT_PLAN.md` только когда обе текущие коллекции либо:

1. имеют evidence-backed `review_status = cleared`; либо
2. удалены/заменены так, что неочищенные файлы больше не входят в распространяемый пакет.

До этого coverage automation считается завершённой частью задачи, но сама `SEC-05` остаётся
открытой.
