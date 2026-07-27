# Build manifest — GEOLOG GASRATIO@Pixler 0.7.83

## Package

- Package version: `0.7.83`
- Python: `>=3.11`
- Project format: `v20`
- Form schema: `v8`
- Tablet layout: `v18`

## Increment

- corrected GeoScape GSWITS header items `01–07`;
- source sequence moved from item `02` to item `04`;
- complete 963-field GeoSensor WITS Level 0 catalog for records `1–25`;
- reviewed profile remains authoritative for UOM, index and aggregation, with catalog fallback for the wider vendor field surface;
- deterministic catalog generator with ZIP path, encoding, column and duplicate-key validation;
- read-only Windows MDB export helper for selected GSWITS reference tables;
- vendor reference hashes, static analysis, derived dictionaries and manual-frame fixture;
- live/replay regression coverage for actual GSWITS-shaped data;
- updated ETP I.2 interoperability gate and matrix template;
- original vendor binaries, databases, archives and manuals excluded from distributable artifacts.

## Validation

- Targeted release gate: `214 passed, 5 skipped in 1.85s`.
- Documentation tests: included in the targeted gate; documentation audit passed.
- Documentation audit: `116` localized Markdown files per language and `2224` equal RU/KK/EN i18n keys.
- Byte-code compilation: `python -m compileall -q src tests tools scripts` passed.
- Full collection attempt: `1338 tests collected, 83 collection errors in 4.02s`.
- All collection errors are caused by unavailable Qt runtime dependencies (`PySide6`/`pyqtgraph`) in the Linux build container; the full GUI suite is not claimed as passed.
- Wheel ZIP integrity, package metadata version and required WITS resources passed.
- Isolated `--no-deps` wheel installation and headless catalog smoke import passed (`0.7.83`, `963` fields, sequence item `04`).
- Ruff was not available in the build environment and is not claimed as passed.
- GeoScape executables, libraries and databases were not executed; analysis remained static and read-only.
- Real Windows GSWITS and ETP interoperability/soak gates remain external acceptance tasks.

## Reference inputs

- `GeoScape2.zip` SHA-256: `b9b358b76e1956058421ce6969ff04a0c961a986160dc2f207d2bfa5a921cf44`.
- `GSWITSProxy Manual(1).pdf` SHA-256: `5d3e27cf94e022460bc68dfc234591a2c4ea2bfbbe2426f789c8edfd58902c43`.
- `GeoScape/WITS.csv` SHA-256: `35d960785d0a6c25635587125e01ae19a3e6a90209514d9d10997fe56b54b2aa`.
- Generated runtime catalog SHA-256: `18091f167e5010e1cb7803710609974385d83339dae1d44e93e919355c81d616`.

## Artifacts

- Source archive: `GEOLOG_GASRATIO_Pixler_0.7.83_GeoScape_WITS_Compatibility.zip`
- Wheel: `geolog_gasratio_pixler-0.7.83-py3-none-any.whl`
- Integration plan: `GEOLOG_GASRATIO_Pixler_WITS_Integration_Plan_0.7.83.md`
- Vendor reference pack: `GEOLOG_GASRATIO_Pixler_GeoScape2_WITS_Reference_0.7.83.zip`
- Updated ETP I.2 gate: `GEOLOG_GASRATIO_Pixler_ETP12_Interoperability_Gate_0.7.83.md`
- ETP interoperability matrix template: `GEOLOG_GASRATIO_Pixler_ETP12_Interoperability_Matrix_0.7.83.csv`
- WITS0 Windows field gate: `GEOLOG_GASRATIO_Pixler_WITS0_Windows_Field_Gate_0.7.83.md`
- Compatibility smoke report: `GEOLOG_GASRATIO_Pixler_GeoScape_WITS_Compatibility_Smoke_0.7.83.json`
- Consolidated release bundle: `GEOLOG_GASRATIO_Pixler_0.7.83_Release_Bundle.zip`
