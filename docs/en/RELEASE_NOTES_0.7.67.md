# GEOLOG GASRATIO@Pixler 0.7.67 — compact parameter-labelled curve rulers

## What changed

- Removed the redundant generic **Scale** caption from numeric curve headers.
- The ruler is now labelled directly with the localized parameter name and unit, for example
  **Weight on bit · t**.
- Removed the separate duplicated curve-title row. One parameter block is now 44 px instead of
  58 px, saving 14 px or about 24% of vertical header space.
- Preserved editable minimum/unit/maximum fields, automatic range, settings, mandatory endpoints,
  grid ticks, linear/logarithmic behaviour, and complete-row internal scrolling.
- The shared `TabletTrackWidget` applies the change to all factory, ready, and user forms without
  manually editing every template.

## Compatibility

- Project format remains `v20`.
- Form schema remains `v8`.
- Tablet layout remains `v18`.
- Existing forms, widths, ranges, units, styles, and bindings are not rewritten.
- The root `README.md` remains concise and unchanged.

## Verification

Regression coverage checks the 44 px complete-row geometry, parameter-name ruler caption, removed
legacy localization key, preserved action controls, RU/KK/EN documentation parity, and version
contract. Full visual Qt verification still requires Windows with PySide6 and pyqtgraph.
