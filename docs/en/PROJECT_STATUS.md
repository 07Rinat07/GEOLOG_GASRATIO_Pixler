# Project status

Snapshot: 23 July 2026. Package version 0.7.33, test build.

## Release decision

The last complete baseline is 0.7.28: Ruff passes, mypy reports zero errors across 262 source
files, and full pytest reports 1,217 passed and 10 skipped. For 0.7.33, `compileall` and the
available headless/regression/source-integrity suite completed with 731 passed and 4 skipped.
Three LAS round-trip tests require `lasio`, one Qt scenario requires `PySide6`, and full
collection also needs PySide6, pyqtgraph, and lasio. Ruff and mypy are unavailable in this
container. The build remains a test build until the full gate and the mandatory
Windows/HiDPI/PDF/physical-printer matrix pass.

## Verified foundation

- safe LAS 1.2/2.0, CSV/TXT, Excel, and GeoScape/Paradox workflows;
- multi-dataset and multi-index project format v16;
- Semantic Channel Dictionary plus explicit UOM quantity classes;
- persisted semantic binding for every curve;
- one interactive Import Review for CSV, Excel, LAS, and Paradox;
- index selection/validation, manual semantic and UOM overrides, and an additional NULL sentinel;
- QC for NULL, duplicate, gap, order, unresolved, UOM conflict, all-NULL, and duplicate kind;
- atomic acceptance through a deep-copy controller and project-session port;
- multi-track tablet, forms, Masterlog, PDF, Print Center, annotations, and project assets;
- synchronized RU/KK/EN user documentation.

## Current-slice verification

| Check | Result |
|---|---|
| Import Review controller | initial plan, preview, and commit do not mutate the source dataset |
| Import jobs | CSV, Excel, LAS, and Paradox invoke review before project registration |
| Cancellation | creates no dataset/well and does not change `dirty` |
| QC | blocking errors disable commit; warnings remain visible |
| Localization | RU/KK/EN catalogs contain the same 1733 keys |
| Available regression | 731 passed, 4 skipped |
| Project format | remains v16 |

## Highest-risk technical debt

- `tablet/tablet_view.py` and `ui/main_window.py` remain large orchestration classes;
- the full Ruff/mypy/Qt/LAS gate must be repeated for 0.7.33 in the complete environment;
- the interactive dialog needs a manual Windows large-table and HiDPI test;
- shared screen/print golden fixtures are still missing;
- a UOM edit in Import Review corrects metadata but does not convert values.

## Next checkpoint

The next vertical slice is Report Passport: source fingerprint, semantic bindings, formula
versions, UOM, form revision, locale, and render settings. Golden fixtures follow. The manual
Windows GUI/HiDPI/PDF/physical-printer smoke test remains mandatory for a stable release.

See [Import Review](IMPORT_REVIEW.md),
[Semantic Channel Dictionary](SEMANTIC_CHANNEL_DICTIONARY.md), and the
[plan](PROJECT_PLAN.md).
