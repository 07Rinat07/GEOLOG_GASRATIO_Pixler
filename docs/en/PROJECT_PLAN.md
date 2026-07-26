# Project plan

Current on 27 July 2026 after the 0.7.74 slice. This file contains unfinished work only; implemented increments belong in
[project status](PROJECT_STATUS.md), the root [changelog](../CHANGELOG.md), and release notes.


## Priority: WITS0 Import Review and live acquisition

Raw capture and the typed parser are complete. Remaining work:

- [ ] obtain 5–10 minutes of real GSWITS raw data;
- [ ] confirm TCP mode, address, port, encoding, header fields, and record intervals;
- [ ] compare the built-in GeoScape profile with real record/item values;
- [ ] add Import Review for channel/UOM/index mapping;
- [ ] preserve versioned user profile overrides;
- [ ] create an immutable AcquisitionDatasetSchema after mapping confirmation;
- [ ] create an append-only AcquisitionSession and live time/depth graphs;
- [ ] complete Windows reconnect/soak/restart validation.
## GeoScape II GS2 acceptance

- [ ] add versioned projections and anonymized Access/Paradox fixtures from other GeoScape versions;
- [ ] cover damaged, truncated, and multipart tables with reproducible golden fixtures;
- [ ] compare СГ-8 and at least two other GS2 files with reference GeoScape LAS/Excel exports;
- [ ] confirm C1–C5, total gas, TIME/DEPTH, units, ranges, and file splitting;
- [ ] verify Gas Ratio/Pixler on channels proven through `GS2.mdb`.

The automated numeric-TIME CSV/XLSX test confirms the shared resolved-export path but does not
replace comparison with real reference LAS/Excel output.

## Manual 0.7.72 acceptance

- [ ] verify both command rows on Windows at 100%, 125%, and 150% DPI;
- [ ] move the window between a laptop and external monitor, including F4 and repeated actions;
- [ ] verify transparent and original symbols with all eight handles, **Shift**, and rotation;
- [ ] confirm reselect, move, and resize of an ultra-thin symbol after **Ctrl+S** and reopen;
- [ ] compare screen, preview, PDF, and physical print for `0.01` logical-pixel geometry.

## Release recovery

- [ ] resolve the current mypy findings and internal error;
- [ ] complete the signed tablet/annotation/PDF/HiDPI/physical-printer smoke checklist;
- [ ] publish a stable build only after the mandatory gate is green.

## Acceptance criterion

The window stays inside the active monitor work area, the right editing command remains available,
and an ultra-thin symbol remains visible, selectable, and editable without changing stored
geometry. CSV/XLSX use the exact rows of the active numeric DEPTH/TIME axis.
