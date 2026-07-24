# Project status

24 July 2026: package **0.7.61**, project format **v20**, form schema **v6**, tablet layout **v16**.

## Completed in 0.7.61

- added a dedicated command for inserting built-in catalog symbols on tablet graphs;
- the picker provides thumbnails, localized names, categories, and search;
- users can select a cropped transparent image or the original background-preserving variant;
- track, curve/depth anchor, exact depth, and initial size are selected before insertion;
- the inserted object supports left-button dragging and resizing through eight handles;
- each symbol is stored in project-owned image storage with its catalog ID and background mode;
- existing Undo/Redo, project persistence, PDF, and printing are reused without a parallel format;
- documentation and instructions are synchronized in Russian, Kazakh, and English;
- the root README remains free of technical release history.

## Verification

Available container verification: **103 focused tests passed**; `compileall` succeeded. The full
Qt/UI run was not available because PySide6, pyqtgraph, and lasio are missing; complete automated
and manual verification remains mandatory in the installed Windows project environment.

## Next vertical slice

Read-only offline WITSML 2.1 inventory and mapping fixtures.
