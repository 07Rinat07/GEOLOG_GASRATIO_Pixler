# GEOLOG GASRATIO@Pixler 0.7.83 — GeoScape WITS compatibility

The GSWITS standard header is corrected: `01` well, `02` sidetrack/hole section, `03` record ID,
`04` sequence, `05` date, `06` time, and `07` activity. Sequence tracking, gaps, duplicates, and
provenance now use item `04`.

A complete derived GeoSensor WITS Level 0 catalog is included: 963 fields, records 1–25, declared
types, and mnemonics. A reproducible tool builds it from `GeoScape/WITS.csv`; vendor EXE/BPL/MDB/PDF
files are not included in the wheel or source archive. Project format `v20`, form schema `v8`, tablet
layout `v18`, the ready user template, and compact limits 50%, 48, and 80 remain unchanged.
