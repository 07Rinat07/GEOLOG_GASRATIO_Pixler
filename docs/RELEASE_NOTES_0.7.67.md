# GEOLOG GASRATIO@Pixler 0.7.67 — compact parameter-labelled curve rulers

## What changed

- Removed the redundant generic `Scale` caption from numeric curve headers.
- The engineering ruler is now labelled directly with the localized parameter name and unit,
  for example `Weight on bit · t`.
- Removed the separate duplicated curve-title row. One parameter block is now 44 px instead of
  58 px, saving 14 px or about 24% of vertical header space.
- Kept editable minimum/unit/maximum fields, automatic range, curve settings, mandatory scale
  endpoints, grid ticks, linear/logarithmic behaviour, and complete-row internal scrolling.
- The shared `TabletTrackWidget` renderer applies the change to factory, ready, and user forms;
  no form JSON migration is required.

## Compatibility

- Project format remains `v20`.
- Form schema remains `v8`.
- Tablet layout remains `v18`.
- Existing forms, widths, curve ranges, units, styles, and bindings are not rewritten.
- The root `README.md` remains concise and unchanged.

## Verification

Regression coverage checks the 44 px complete-row geometry, curve-name ruler caption, removed
legacy localization key, preserved action controls, multilingual documentation parity, and
version contract. Full visual Qt verification still requires the Windows runtime with PySide6
and pyqtgraph.
