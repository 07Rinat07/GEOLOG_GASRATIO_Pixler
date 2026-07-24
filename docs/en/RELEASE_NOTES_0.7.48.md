# GEOLOG GASRATIO@Pixler 0.7.48 — engineering curve scale and header units

Test build dated 24 July 2026. Project format remains v20, form schema remains v6, and tablet
layout advances from v15 to v16.

## Parameter header

- minimum and maximum remain editable directly in the header;
- a visible colored ruler now shows major and minor divisions;
- ruler positions match the normalized vertical grid of that specific column;
- intermediate labels are calculated correctly for linear and logarithmic scales;
- both limits can be prepared before applying them with `✓` or Enter;
- `A` restores automatic range.

## Unit and scale type

- the display unit is visible and editable directly in the header;
- linear/logarithmic mode can be switched there as well;
- the unit is a presentation override and does not convert numeric samples;
- the full curve settings dialog exposes the same unit field;
- unit, range, scale type, colors, and grid divisions persist in the working form;
- legacy tablet layout v15 migrates to v16 with `unit_override = null`, preserving source metadata
  behavior.

## Verification

- focused header/form/import suite: **152 passed, 3 skipped, 3 deselected**;
- available headless regression: **1020 passed, 4 skipped, 3 deselected**;
- `compileall` passed;
- Windows/PySide6 visual smoke testing remains required for narrow columns and HiDPI.
