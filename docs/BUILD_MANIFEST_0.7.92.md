# Build manifest — GEOLOG GASRATIO@Pixler 0.7.92

## Package

- Package version: `0.7.92`
- Python: `>=3.11`
- Canonical startup: `python -m geoworkbench.app.main`
- Project format: `v21`
- Form schema: `v11`
- Tablet layout: `v21`

## Increment

- automatic font fitting for long 90-degree tablet captions;
- 96 px synchronized rotated-title band;
- horizontal LBA default in factory forms, new tracks and migrations;
- synchronized form-column and tablet-track title presentation;
- migrations from form schema v10 and tablet layout v20;
- updated RU/KK/EN release notes and current documentation navigation.

## Validation performed in the available container

- `python -m compileall -q src tests tools scripts` — passed;
- `python tools/check_documentation.py` — passed;
- focused compact-column, form, layout and version tests — 88 passed;
- `python scripts/run_headless_tests.py` — 1373 passed, 15 skipped;
- Qt collection remains reduced only because PySide6, pyqtgraph and lasio are not installed in the container.

## Validation not performed in this container

- actual PySide6 GUI startup and screenshot comparison;
- full Windows DPI matrix;
- physical printing acceptance.

## Artifacts

- Source archive: `GEOLOG_GASRATIO_Pixler_0.7.92_COMPACT_HEADERS_FIT_LBA_HORIZONTAL.zip`
- SHA-256: `GEOLOG_GASRATIO_Pixler_0.7.92_COMPACT_HEADERS_FIT_LBA_HORIZONTAL.zip.sha256`
- Technical report: `HOTFIX_REPORT_0.7.92.md`
