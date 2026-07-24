# Project plan

Current as of 25 July 2026. Version **0.7.64** uses project format v20,
form schema v7, and tablet layout v17.

## P0 — forms, compact columns, and clear naming

- [x] reduce Stratigraphy, Lithology, Cuttings, Calcimetry, LBA, and Depth widths by 40%;
- [x] allow those columns to be adjusted manually from 48 px;
- [x] retain the 80 px minimum for ordinary graph and text columns;
- [x] process factory and legacy user forms through one-time migration;
- [x] keep the protected template set free of duplicate MASTERLOG forms;
- [x] open a complete reference of existing names and details while creating a form;
- [x] add search across names, descriptions, columns, and parameters;
- [x] block duplicate names regardless of case and extra whitespace;
- [x] update RU/KK/EN instructions and documentation;
- [x] add regression tests;
- [ ] run a Windows/PySide6 smoke test at 100/125/150% DPI covering form creation, search,
  selection, details, duplicate blocking, save/reopen, width editing, preview, PDF, and physical
  printing.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation of daily growth;
- [ ] secured ETP 1.2 after successful fixture replay.
