# Project plan

Current on 24 July 2026. Version **0.7.61** keeps project format v20, form schema v6, and tablet layout v16.

## P0 — 0.7.61: insert catalog symbols on graphs

- [x] add a dedicated Insert symbol command to the F4 toolbar and graph context menu;
- [x] open the built-in catalog with thumbnails, localized names, categories, and search;
- [x] offer cropped transparent and original background-preserving variants;
- [x] select a track, curve parameter, or depth-only anchor;
- [x] set exact depth and initial size before insertion;
- [x] persist the catalog ID and background mode in the annotation model;
- [x] copy the image into project-owned storage without an external path;
- [x] reuse left-button movement, eight resize handles, and Undo/Redo;
- [x] synchronize RU/KK/EN documentation and instructions;
- [x] add regression tests for the model, catalog, integration, and localization;
- [ ] Windows/PySide6: verify insertion, drag/resize, reopen, PDF, and printing at 100%, 125%, and 150% DPI.

Exit criterion: a symbol can be selected from the catalog, anchored to the required depth/parameter,
persisted in the project, and adjusted precisely with the mouse without damaging the form or graphs.

## Next stages

- [ ] read-only offline WITSML 2.1 inventory and mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays in one form;
- [ ] directory watcher with preview confirmation for daily growth;
- [ ] secured ETP 1.2 only after successful fixture replay.
