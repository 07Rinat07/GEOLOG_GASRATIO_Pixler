# Build manifest 0.7.64

Version 0.7.64 is built from the user's supplied 0.7.62 local project archive plus the retained
0.7.61 symbol feature, the complete 0.7.62 documentation audit, and the 0.7.63 compact-column
implementation. Project format remains v20, form schema remains v7, and tablet layout remains v17.
The root `README.md` remains concise.

## Included changes

- retained the synchronized RU/KK/EN documentation set and automated documentation checker;
- retained graph-symbol insertion, persistence, mouse positioning, resizing, and save/reopen guides;
- retained 40% compact widths and the 48 px minimum for Depth, Stratigraphy, Lithology, Cuttings,
  Calcimetry, and LBA, with 80 px retained for ordinary graph and text tracks;
- preserved the existing protected factory template set without adding a duplicate MASTERLOG form;
- replaced the blind form-name prompt with a full library-reference dialog;
- listed all built-in and user forms with search, axis, origin, descriptions, column widths,
  tracks, parameters, and mnemonics;
- normalized accidental whitespace and blocked case-insensitive duplicate form names;
- added dependency-free naming tests, source-contract tests, GUI tests, and documentation coverage.

## Verification scope

The package is checked with 112 focused non-Qt regression tests, source contracts,
localized documentation audit, `compileall`, package build, and ZIP integrity. GUI tests are included
for Windows/PySide6 execution. Complete visual mouse, HiDPI, PDF, and physical-printer validation
remains a Windows gate with PySide6, pyqtgraph, and lasio installed.

## Root README policy

The root README contains only current project overview, requirements, quick start, basic use, and
links. Detailed implementation notes and test history remain under `docs`.
