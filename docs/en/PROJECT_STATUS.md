# Project status

25 July 2026. Package version: **0.7.64**. Project format: **v20**,
form schema: **v7**, tablet layout: **v17**.

## Completed in 0.7.64

- retained the 0.7.63 compact Stratigraphy, Lithology, Cuttings, Calcimetry, LBA, and Depth columns
  and the form-schema v6 → v7 and tablet-layout v16 → v17 migrations;
- kept the existing protected template set without adding a duplicate MASTERLOG template;
- **Create form** no longer opens a blind small name prompt;
- the new window lists every built-in and user form with search, axis, and origin columns;
- selecting a form shows its description, column widths, tracks, parameters, and mnemonics;
- duplicate names are blocked regardless of letter case or repeated whitespace;
- accidental whitespace in a new name is normalized automatically;
- user guides and feature maps are synchronized in Russian, Kazakh, and English;
- the root README remains concise and contains no detailed release history.

## Verification

Coverage includes dependency-free name normalization and duplicate detection, source-contract
checks for the new dialog, GUI scenarios for listing forms and blocking duplicates, the absence of a duplicate
MASTERLOG template, and compact-width behavior. Complete visual Qt/UI, HiDPI, PDF, and physical
printer verification remains a Windows gate with PySide6, pyqtgraph, and lasio installed.

## Next stage

After the Windows smoke test, continue the approved plan with read-only offline WITSML 2.1
inventory and mapping fixtures.
