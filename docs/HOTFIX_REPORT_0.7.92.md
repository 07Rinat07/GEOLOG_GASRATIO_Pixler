# HOTFIX REPORT 0.7.92 — compact caption fitting and LBA orientation

## Reported issue

After rotating compact tablet headers by 90 degrees, the long Russian captions
`Стратиграфия` and `Шламограмма` were still slightly clipped. The short `ЛБА`
caption was also unnecessarily rotated.

## Root cause

`OrientedTextLabel` used `TextWordWrap`. Qt does not split a long single word,
so a word wider than the rotated title rectangle was clipped. The title band was
fixed at 88 px and no font-metric fitting was applied.

## Fix

- rotated titles are rendered as one line;
- `QFontMetricsF.horizontalAdvance()` measures the real glyph width;
- font size is reduced only when required and may be slightly condensed to
  absorb platform font-metric differences;
- synchronized rotated title height is 96 px;
- LBA defaults to horizontal in factory forms, new tracks and migrations;
- long compact kinds remain vertical: Depth/Time, Stratigraphy, Lithology,
  Cuttings and Calcimetry;
- form schema advanced to v11 and tablet layout to v21.

## Validation

- focused regression suite: 88 passed;
- source compilation: passed;
- documentation audit: passed after synchronization;
- reduced-environment headless suite: 1373 passed, 15 skipped;
- actual PySide6 rendering remains a Windows GUI acceptance item because the
  container does not include PySide6.
