# GEOLOG GASRATIO@Pixler project status

Snapshot: 25 July 2026. Package version: **0.7.66**. Project format: **v20**,
form schema: **v8**, tablet layout: **v18**.

## Completed in 0.7.66

- the ordinary Form Library and the create/save windows now use one catalog; Ready forms, all
  **18 factory** forms, and user forms appear everywhere;
- the mismatch between the library's curated subset and the save dialog's full list is removed;
- the main toolbar and **Form editing (F4)** toolbar are responsive: secondary commands switch to
  icon-only mode while the right-side toggle remains visible;
- **Clear diagnostics data…** adds confirmation, safe log/report cleanup, and automatic logging
  restart;
- import-diagnostics retention is limited to the newest 30 reports of each type;
- instructions and release notes are updated in Russian, Kazakh, and English.

## Retained from 0.7.65

The complete form-naming dialog, four-local-form migration, compact geological columns, form schema
v8, and tablet layout v18 remain unchanged.

## Verification

Regression tests cover the unified catalog, toolbar adaptation, and diagnostics cleanup. A complete
visual Qt/UI run still requires a Windows environment with PySide6 and pyqtgraph.
