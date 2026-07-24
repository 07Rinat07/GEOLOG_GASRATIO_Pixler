# Release notes 0.7.62 — multilingual documentation audit

Version 0.7.62 is a documentation-quality and verification increment. It does not change project
format v20, form schema v6, or tablet layout v16.

## Delivered

- added a localized feature map in `docs/ru`, `docs/kk`, and `docs/en`;
- documented the common save model for project data, forms, intervals, annotations, and symbols;
- expanded catalog-symbol instructions with save, close, reopen, Undo/Redo, delete, lock, print,
  PDF, and project-owned image behavior;
- synchronized current user guides, status, plan, release notes, and navigation in RU/KK/EN;
- added a dependency-free documentation checker for localized file parity, relative links, i18n
  key parity, package/release version alignment, and required save/reopen workflows;
- added regression tests for the documentation checker;
- kept the root README concise and free of release-level implementation details.

## Verification boundary

Documentation audit passed for 82 files per language and 1881 i18n keys. The available headless
suite completed with **1103 passed, 4 skipped, 3 deselected**. Full collection is blocked by 82
modules requiring PySide6, pyqtgraph, or lasio; Windows Qt/UI, LAS, PDF, and printer verification
remains mandatory.
