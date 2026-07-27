# GeoSensor WITS Level 0 compatibility catalog

## Purpose

The built-in `geosensor-wits-level0.json` catalog is derived from the machine-readable
`GeoScape/WITS.csv` file supplied in the GeoScape 2 archive. It contains 963 `record/item` pairs for
records 1–25, descriptions, short/long mnemonics, declared types, and lengths.

The catalog complements the GSWITS profile. The profile supplies reviewed units, aggregation,
index type, and send policy for supported records; the catalog lets the parser recognize the other
standard fields without false `unknown record/item` diagnostics.

## Standard header

- `01` — Well Identifier;
- `02` — Sidetrack/Hole Section Number;
- `03` — Record Identifier;
- `04` — Sequence Identifier;
- `05` — Date;
- `06` — Time;
- `07` — Activity Code.

The source sequence number is read only from item `04`.

## Reproducibility and boundary

The catalog is rebuilt with `tools/build_geosensor_wits_catalog.py`. The tool validates ZIP paths,
reads only `GeoScape/WITS.csv`, and never executes vendor binaries. Original EXE, BPL, MDB, FDB,
and PDF files are excluded from the wheel and source archive. Hashes and analysis are stored in
[reference_manifest.json](../../vendor_reference/geosensor_geoscape2/inventory/reference_manifest.json)
and [ANALYSIS_GEOSCAPE2_WITS.md](../../vendor_reference/geosensor_geoscape2/analysis/ANALYSIS_GEOSCAPE2_WITS.md).
