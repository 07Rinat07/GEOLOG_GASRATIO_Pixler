# Build manifest — GEOLOG GASRATIO@Pixler 0.7.66

## Package

- Package version: `0.7.66`
- Project format: `v20`
- Form schema: `v8`
- Tablet layout: `v18`
- Root `README.md`: unchanged

## Functional changes

- one authoritative full form catalog for browse/create/save workflows;
- 18 visible factory forms in the ordinary Form Library;
- responsive main and form-editing toolbars;
- safe diagnostics cleanup with automatic logging restart;
- import diagnostics retention limited to 30 reports per prefix.

## Verification

- documentation audit: 86 localized Markdown files per RU/KK/EN language;
- localization parity: 1887 keys per RU/KK/EN catalog;
- available dependency-free regression suite: 1135 passed, 4 skipped;
- 3 LAS-dependent tests were deselected because `lasio` is unavailable in the build container;
- Qt/pyqtgraph UI modules require a Windows environment with project dependencies installed;
- `compileall` completed for `src`, `tests`, and `tools`;
- wheel `geolog_gasratio_pixler-0.7.66-py3-none-any.whl` built successfully with
  SHA-256 `4a842a96b41572b36f598512d3d1c3b4ccfd5c361276b0cb997b166a95dde45c`.
