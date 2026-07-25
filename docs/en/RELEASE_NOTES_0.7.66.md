# GEOLOG GASRATIO@Pixler 0.7.66 — unified catalog, diagnostics cleanup, and responsive toolbars

## Changes

- **Form library**, **Create form**, and **Save user form** now use one authoritative catalog:
  Ready forms, all **18 factory** forms, and user forms are identical in every window.
- The mismatch where the full factory set appeared only during saving while the ordinary library
  showed a curated subset has been removed.
- The main top toolbar and the **Form editing (F4)** toolbar are responsive. When width is limited,
  secondary commands become icon-only buttons so the right-side editing toggle remains inside the
  window.
- **Help → Clear diagnostics data…** now removes accumulated logs and import reports after
  confirmation, then resumes logging automatically.
- Automatic import-report retention is limited to the newest 30 files of each type.

## Cleanup safety

Cleanup does not touch projects, LAS files, user forms, settings, or diagnostics ZIP bundles
exported by the user.

## Compatibility

Project format remains **v20**, form schema **v8**, and tablet layout **v18**.
