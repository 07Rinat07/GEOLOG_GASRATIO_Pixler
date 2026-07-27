# Build manifest — GEOLOG GASRATIO@Pixler 0.7.81

## Package

- Package version: `0.7.81`
- Python: `>=3.11`
- Project format: `v20`
- Form schema: `v8`
- Tablet layout: `v18`

## Increment

- secure ETP v1.2 binary WebSocket client with `etp12.energistics.org`;
- RequestSession/OpenSession protocol negotiation;
- read-only Discovery, Store and Data Array facade;
- Channel Streaming receive path and recoverable Channel Subscribe;
- request correlation, multipart FIN and automatic acknowledgement;
- bounded reconnect watchdog and subscription restore;
- dedicated credential namespace and hash-chained audit;
- QThread/asyncio desktop browser and live channel table.

## Validation

The targeted headless gate completed with `149 passed`. Documentation audit reported 112 localized
Markdown files per language and 2193 synchronized RU/KK/EN keys. `compileall`, wheel build, wheel ZIP
integrity and isolated `--no-deps` package import passed. Full collection discovered 1318 tests and
stopped with 83 PySide6/pyqtgraph import errors. The generated ETP runtime packages were unavailable
from the build container package index, so real Avro wire and Windows GUI interoperability remain
external acceptance gates.

## Artifacts

- Source archive: `GEOLOG_GASRATIO_Pixler_0.7.81_ETP12.zip`
- Wheel: `geolog_gasratio_pixler-0.7.81-py3-none-any.whl`
- Integration plan: `GEOLOG_GASRATIO_Pixler_WITS_Integration_Plan_0.7.81.md`
- Gate checklist: `GEOLOG_GASRATIO_Pixler_ETP12_Interoperability_Gate_0.7.81.md`
