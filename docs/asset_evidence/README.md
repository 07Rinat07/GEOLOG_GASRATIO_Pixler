# SEC-05 asset clearance evidence

Этот каталог предназначен только для **санитизированных, проверяемых записей** о праве
распространять встроенные constructor assets. Наличие файла здесь само по себе не означает
clearance: `tools/check_asset_provenance.py` сверяет запись с provenance и asset manifest.

## Формат записи

Для каждой коллекции со статусом `review_status = "cleared"` поле `evidence_reference` в
`src/geoworkbench/resources/asset-provenance.json` должно содержать относительный путь к JSON-файлу
в этом каталоге, например `constructor-lithology.json`.

Минимальная схема:

```json
{
  "schema": "geolog.asset-clearance-evidence.v1",
  "collection_id": "constructor-lithology",
  "source_archives": ["example.zip"],
  "rights_holder": "Verified rights holder",
  "license_basis": "Written permission for redistribution",
  "evidence_kind": "written-permission",
  "evidence_locator": "internal-record:SEC-05/2026-09-02/001",
  "reviewed_by": "Reviewer name or role",
  "reviewed_at_utc": "2026-09-02T00:00:00Z"
}
```

Validator требует:

- schema `geolog.asset-clearance-evidence.v1`;
- точное совпадение `collection_id`;
- точное совпадение набора `source_archives` с provenance;
- совпадение `rights_holder` и `license_basis` с provenance;
- непустые строковые `evidence_kind`, `evidence_locator`, `reviewed_by`, `reviewed_at_utc`;
- JSON-файл должен физически находиться внутри `docs/asset_evidence`; absolute paths,
  `..`, пустые сегменты и Windows backslash-пути не принимаются.

## Что хранить нельзя

Не коммитьте сюда персональные документы, подписи, секреты, токены, приватную переписку или
непубличные договоры целиком. В публичной evidence-записи фиксируется только достаточный
санитизированный факт проверки и стабильный locator на внутренний/внешний документ, который
может быть предъявлен при юридическом review.

## Текущее состояние

На 2 сентября 2026 года `constructor-lithology` и `constructor-symbols` остаются `unresolved`:
для архивов `Litol_Bmp(2).zip`, `Litol2_Bmp(2).zip` и `Значки(2).zip` в репозитории нет
archive-specific evidence, достаточного для изменения статуса на `cleared`.
