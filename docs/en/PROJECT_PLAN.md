# Project plan

Current as of 24 July 2026. Hotfix **0.7.54** keeps project format v20, form schema v6 and
tablet layout v16.

## P0 — fixed curve headers, readable scales and consistent parameter identity

- [x] remove the linear/log selector from the working header and keep it in full settings;
- [x] give editable and plain curve headers one identical fixed height;
- [x] prevent scale changes from modifying header geometry or synchronized bands;
- [x] label the ruler as “Scale · unit” without duplicating the mode;
- [x] always render endpoints and add intermediate labels only when width permits;
- [x] darken very light ruler colours against the white paper background;
- [x] use readable parameter name plus mnemonic in hover, tooltips and pencil readouts;
- [x] force a readable QToolTip palette and transparent helper-label backgrounds;
- [x] cover the contract with focused and headless regression tests;
- [ ] Windows/PySide6: verify mixed curve counts, 80–400 px tracks, settings-driven scale
  switches, hover and 100/125/150% DPI.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays;
- [ ] directory watcher with preview confirmation;
- [ ] secured ETP 1.2 after fixture replay.
