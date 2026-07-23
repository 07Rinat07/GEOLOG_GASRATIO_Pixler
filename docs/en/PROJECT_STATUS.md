# Project status

Snapshot: 23 July 2026. Version 0.7.32, test build.

## Release decision

The last complete 0.7.28 baseline is green: Ruff passes, mypy reports zero errors across
262 source files, and full pytest reports 1,217 passed and 10 skipped. For 0.7.32,
`compileall`, wheel packaging, and the available headless regression completed with 707 passed
and 4 platform-specific skips. Full pytest collection stops at 95 Qt/LAS-dependent modules
because this container lacks PySide6, pyqtgraph, and lasio; Ruff and mypy are unavailable as
well. The build remains a test build until the full gate and Windows/HiDPI/PDF/physical-printer
matrix pass.

## Working foundation

- safe LAS/CSV/TXT/Excel/Paradox import and edit workflows;
- multi-dataset and multi-index projects using project format v16;
- one Semantic Channel Dictionary and an explicit UOM quantity-class dictionary;
- a persisted per-curve binding with source mnemonic/UOM, sensor, confidence, and evidence;
- read-only Import Review for index, NULL, unresolved, UOM conflict, and duplicates;
- multi-track tablet, forms, Masterlog, PDF, Print Center, annotations, and project assets;
- synchronized RU/KK/EN user documentation.

The same semantic resolver serves CSV/Excel, LAS, and Paradox, and bindings survive copy, merge,
resample, and TIME↔DEPTH operations. Legacy projects are enriched during read without replacing
an already stored canonical mnemonic.

The next slice is an interactive Import Review with manual overrides and atomic acceptance.

See the [Semantic Channel Dictionary](SEMANTIC_CHANNEL_DICTIONARY.md),
[audit](PRODUCT_AUDIT_2026.md), and [plan](PROJECT_PLAN.md).
