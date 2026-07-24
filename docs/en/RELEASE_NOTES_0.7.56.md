# GEOLOG GASRATIO@Pixler 0.7.56 — form-width guidance and adaptive statistics

- Added one deterministic width audit against the usable portrait and landscape A4 width at 96 DPI.
- The Form Library reports column count, px/mm width, expected fit percentage, and an actionable recommendation.
- The structure editor refreshes the A4 indicator immediately after column add/remove/resize operations.
- The editor preview draws portrait and landscape A4 boundaries when the form exceeds them.
- The tablet status bar continuously reports whether the form fits portrait, prefers landscape, needs Fit, or should be split.
- Interval statistics no longer remain as an off-screen floating window: the panel docks right on wide screens and bottom on narrow screens.
- Bottom mode uses wider numeric columns and compact height; side mode uses a narrow adaptive table.
- Diagnostics now include current form width and portrait/landscape A4 percentages.
- Package **0.7.56**; project format **v20**; form schema **v6**; tablet layout **v16**.

## Verification

- focused width/layout/source-contract: **13 passed**;
- available headless regression: **1069 passed, 4 skipped, 3 deselected**;
- `compileall`: passed;
- Windows/PySide6 visual smoke test remains required for dock transitions and 100/125/150% DPI.
