# Build manifest — GEOLOG GASRATIO@Pixler 0.7.93

## Package

- Package version: `0.7.93`
- Canonical startup: `python -m geoworkbench.app.main`
- Project format: `v21`
- Form schema: `v11`
- Tablet layout: `v21`

## Main changes

- Runtime translation of known factory track captions and merged section headers.
- Runtime translation of standard technology parameter captions through the factory dictionary and Sensors catalog.
- Active-language catalog lithotype names in cursor summaries, cuttings composition and rock-description fallbacks.
- Conservative exact-name translation for catalog rocks while preserving free-form geology and custom captions.
- Numeric suffix preservation for automatically split columns such as `Бурение 2`.

## Executed validation

- Focused localization/form/layout/version suite: **106 passed**.
- Reduced-environment headless suite: **1379 passed, 15 skipped**.
- Desktop test collection excluded **83 files** because `PySide6`, `pyqtgraph` and `lasio` are not installed in the build container.
- Documentation audit: **120 localized Markdown files per language**, **2228 i18n keys**, no broken current-version contract.
- `python -m compileall -q src`: passed.
- Full Windows Qt GUI acceptance was not executed in this container and remains a local release check.

## Release artifacts

- Source archive: `GEOLOG_GASRATIO_Pixler_0.7.93_RUNTIME_FORM_LOCALIZATION_FIXED.zip`
- SHA-256: `GEOLOG_GASRATIO_Pixler_0.7.93_RUNTIME_FORM_LOCALIZATION_FIXED.zip.sha256`
- Technical report: `HOTFIX_REPORT_0.7.93.md`
