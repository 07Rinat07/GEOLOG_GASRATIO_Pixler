# Project status

24 July 2026. Package version: **0.7.62**. Project format: **v20**,
form schema: **v6**, tablet layout: **v16**.

## Completed in 0.7.62

- audited the main user-facing features and their instructions;
- added a [feature map](FEATURES.md) linking to detailed guides;
- documented **Ctrl+S** saving, closing without saving, reopening, Undo/Redo, and the difference
  between export and project saving;
- expanded symbol instructions with selection, anchoring, placement, sizing, saving, restoration,
  deletion, locking, preview/PDF, and printing;
- added an automated audit for RU/KK/EN document parity, links, i18n keys, package version, and
  mandatory user workflows;
- kept the root README concise.

## Verification boundary

Documentation audit: 82 files per language and 1881 i18n keys passed. Available headless suite:
**1103 passed, 4 skipped, 3 deselected**. Complete Qt/UI, LAS, PDF, and printer verification
requires a Windows environment with PySide6, pyqtgraph, and lasio installed.

## Next stage

Read-only offline WITSML 2.1 inventory and mapping fixtures after the Windows smoke test.
