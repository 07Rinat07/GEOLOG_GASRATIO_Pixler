# Build manifest — GEOLOG GASRATIO@Pixler 0.7.65

## Package contract

- Package version: `0.7.65`
- Project format: `v20`
- Form schema: `v8`
- Tablet layout: `v18`
- Supported documentation languages: `ru`, `kk`, `en`
- Root `README.md`: intentionally unchanged and concise

## Included implementation

- full library-reference dialog for Create form and Save user form;
- duplicate-name normalization and editable-form revision workflow;
- automatic protected promotion of four confirmed local form names;
- no separate user-visible factory MASTERLOG duplicate;
- one-time 50% compact-width migration for Stratigraphy, Lithology, Cuttings, Calcimetry, LBA,
  and Depth, with 48 px compact and 80 px standard minimums;
- schema v7 → v8 and layout v17 → v18 migration;
- synchronized RU/KK/EN user guides and automated documentation audit;
- regression tests for naming, promotion, schema/layout migration, printing width, and source path.

## Validation commands

```text
python -m compileall -q src tests tools
python tools/check_documentation.py --root .
pytest -q <non-Qt regression suites>
python -m pip wheel . --no-deps --no-build-isolation -w dist
```

A full UI run is environment-dependent and requires PySide6, pyqtgraph, and lasio.

## Validation result in the build container

- `compileall`: passed for `src`, `tests`, and `tools`;
- documentation audit: passed, 85 localized Markdown files per language and 1881 matching UI keys;
- dependency-independent regression suite: 1131 passed, 4 skipped, 3 LAS-only cases deselected;
- wheel: `geolog_gasratio_pixler-0.7.65-py3-none-any.whl` built successfully with no build isolation;
- full Qt/LAS collection was not available because this container does not provide PySide6,
  pyqtgraph, or lasio.
