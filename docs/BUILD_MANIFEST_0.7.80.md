# Build manifest — GEOLOG GASRATIO@Pixler 0.7.80

## Package

- Package version: `0.7.80`
- Python: `>=3.11`
- Project format: `v20`
- Form schema: `v8`
- Tablet layout: `v18`

## Increment

- read-only WITSML 1.4.1.1 SOAP Store client;
- GetVersion, GetCap and GetFromStore only;
- Well, Wellbore, Log, LogCurveInfo and LogData discovery;
- timeout, bounded retry, response-size guard and audit;
- credentials outside project files;
- remote LogData reuse of WITSML Import Review and atomic Dataset registration.

## Validation

The targeted headless release gate completed with `130 passed, 4 skipped`. It covers WITSML
1.4.1.1 SOAP, WITSML 2.x, WITS0, acquisition, project codec, documentation and version contracts.
`compileall`, wheel build, wheel content inspection and isolated smoke import also passed. Full
collection found 1,301 tests but stopped with 83 import errors because PySide6/pyqtgraph are absent
from the Linux build container; Qt runtime remains a Windows gate.

## Artifacts

- Source archive: `GEOLOG_GASRATIO_Pixler_0.7.80_WITSML1411_SOAP.zip`
- Wheel: `geolog_gasratio_pixler-0.7.80-py3-none-any.whl`
