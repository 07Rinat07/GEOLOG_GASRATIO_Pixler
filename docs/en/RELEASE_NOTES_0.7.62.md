# Release notes 0.7.62 — multilingual documentation audit

Version 0.7.62 improves documentation and automated quality verification. Project format v20,
form schema v6, and tablet layout v16 are unchanged.

## Delivered

- added a current user-feature map with links to detailed instructions;
- explained the shared project-save model for data, forms, intervals, annotations, and symbols;
- expanded symbol instructions with saving, closing, reopening, Undo/Redo, deletion, locking,
  print flag, PDF, and project-owned image storage;
- synchronized the user guide, status, plan, release notes, and navigation;
- added an automated audit for RU/KK/EN document-set parity, internal links, localization keys,
  package version, and required save/reopen workflows;
- added regression tests for the documentation contract;
- kept the root README concise and free of detailed fix history.

## Verification boundary

Documentation audit passed for 82 files per language and 1881 i18n keys. The available headless
suite completed with **1103 passed, 4 skipped, 3 deselected**. Full collection is blocked by 82
PySide6/pyqtgraph/lasio modules; Windows Qt/UI, LAS, PDF, and printer verification remains required.
