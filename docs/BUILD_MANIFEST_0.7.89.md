# Build manifest — GEOLOG GASRATIO@Pixler 0.7.89

## Package

- Package version: `0.7.89`
- Python: `>=3.11`
- Project format: `v21`
- Form schema: `v9`
- Tablet layout: `v19`

## Increment

- safe reconciliation of stale form `vertical_index_id` values after dataset replacement;
- GeoScape2 relative TIME → DATETIME preference retained for absolute timestamp sources;
- explicit depth selection preserved;
- form candidate layout bound before axis reconciliation;
- form rollback follows the same safe path;
- diagnostic event `tablet.vertical_axis.reconciled` added.

## Validation

- 11 focused axis/form-transaction tests passed;
- 37 related Paradox/GeoScape tests passed and 3 were skipped;
- 3 LAS-dependent tests could not run in the container because `lasio` is unavailable;
- source package `compileall` passed;
- documentation audit passed after synchronized RU/KK/EN release notes;
- Qt GUI execution remains a Windows acceptance check because PySide6/pyqtgraph are unavailable in the container.

## Artifacts

- Source archive: `GEOLOG_GASRATIO_Pixler_0.7.89_GS2_FORM_AXIS_FIXED.zip`
- SHA-256: `GEOLOG_GASRATIO_Pixler_0.7.89_GS2_FORM_AXIS_FIXED.zip.sha256`
- Hotfix report: `HOTFIX_REPORT_0.7.89.md`
