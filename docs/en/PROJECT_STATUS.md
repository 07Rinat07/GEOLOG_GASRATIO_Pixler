# Project status

Snapshot: 23 July 2026. Package version: 0.7.34, test build.

## Release decision

The last fully verified automated baseline is 0.7.28: Ruff clean, mypy with zero errors in 262
source files, and full pytest with 1,217 passed and 10 skipped. For 0.7.34, `compileall` and the
available headless/regression/source-integrity suite completed with 742 passed and 4 skipped.
Four additional LAS/Qt scenarios were explicitly deselected because `lasio`/`PySide6` are absent;
full collection reports 95 Qt/LAS import errors. Ruff and mypy are not installed in this container.
The build remains a test build until the full gate and Windows/HiDPI/PDF/physical-print matrix pass.

## Verified foundation

- safe LAS 1.2/2.0, CSV/TXT, Excel, and GeoScape/Paradox workflows;
- multi-dataset/multi-index project format v16;
- Semantic Channel Dictionary, UOM quantity classes, and persisted semantic bindings;
- interactive Import Review with manual overrides, QC, and atomic commit;
- deterministic Report Passport schema v1 with SHA-256 validation;
- multi-track tablet, forms, Masterlog, Print Center, interpretation reports, and annotations;
- synchronized RU/KK/EN user documentation.

## Current increment results

| Check | Result |
|---|---|
| Determinism | unchanged data, form, language, and render settings produce the same digest |
| Interval | only selected channel values inside the actual report interval are hashed |
| Semantic/UOM | complete sensor/source, kind, quantity, UOM, confidence, aliases, and evidence snapshot |
| Sources | import snapshot, embedded LAS, external file, or normalized report data has SHA-256 |
| Formulas | ID, version, provenance, and expression SHA-256 where available |
| Forms | Masterlog uses version; forms/layouts use content-addressed revisions |
| Export | sidecars for Print Center, direct PNG/SVG/PDF, Masterlog, and interpretation PDF |
| JSON validation | modified signed content is rejected |
| Available regression | 742 passed, 4 skipped, 4 dependency-specific scenarios deselected |
| Project format | remains v16 |

## Highest-risk remaining debt

- repeat the full Ruff/mypy/Qt/LAS gate in the complete environment;
- complete the Windows/HiDPI/PDF/physical-print smoke matrix;
- output and sidecar are individually atomic, not one filesystem transaction;
- physical printing computes a digest but has no sidecar because it has no output path;
- shared screen/print golden fixtures are still missing;
- output-file hashing follows the shared `ReportDefinition` pipeline.

## Next checkpoint

Add golden fixtures for screen/print grids, legends, lithotypes, and annotations. The Windows
GUI/HiDPI/PDF/physical-print smoke matrix remains mandatory for stable status.

See [Report Passport](REPORT_PASSPORT.md), [Import Review](IMPORT_REVIEW.md),
[Semantic Channel Dictionary](SEMANTIC_CHANNEL_DICTIONARY.md), and the
[project plan](PROJECT_PLAN.md).
