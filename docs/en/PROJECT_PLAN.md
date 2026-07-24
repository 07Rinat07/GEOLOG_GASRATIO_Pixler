# Project plan

Current as of 24 July 2026. Package 0.7.48 keeps project format v20 and advances tablet layout
to v16. After Windows validation, the next domain slice remains offline WITSML 2.1 inventory.

## Completed corrective hotfix 0.7.48

- [x] show high-contrast editable minimum and maximum at the ruler edges;
- [x] draw a full-width engineering ruler with major/minor ticks;
- [x] reuse the exact divisions saved for the column grid;
- [x] interpolate labels separately for linear and logarithmic scales;
- [x] let users prepare both limits before commit with `✓` or Enter;
- [x] edit display unit and scale type directly in the header;
- [x] keep unit override presentation-only without numeric conversion;
- [x] persist unit/range/scale/colors in layouts and user forms;
- [x] migrate tablet layout v15 to v16 with `unit_override = null`;
- [ ] run Windows/PySide6/HiDPI smoke tests for wide and narrow columns.

## Completed corrective hotfix 0.7.47

- [x] normalize mixed DB index order in the accepted copy only;
- [x] apply one stable permutation to every index and curve;
- [x] expose `index-sorted-copy` diagnostics;
- [x] prefer explicit DEPT/DEPTH/MD for batch DB → LAS while preserving ambiguity safety;
- [x] honor saved profiles and sort before LAS round-trip;
- [x] edit manual min/max directly in ordinary curve headers;
- [x] persist auto/manual range and header colors in the working form;
- [ ] Windows smoke-test D1174.db, BLData.db, batch conversion, and narrow headers.

## Planned follow-ups

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] optional aligned multi-dataset overlays inside one form;
- [ ] directory watcher with preview confirmation;
- [ ] secured ETP 1.2 only after successful fixture replay.
