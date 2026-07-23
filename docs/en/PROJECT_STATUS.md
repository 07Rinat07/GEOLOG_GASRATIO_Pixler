# Project status

Snapshot: 23 July 2026. Package version: 0.7.35, test build.

## Release decision

The last fully verified baseline is 0.7.28: Ruff clean, mypy with zero errors in 262 source
files, and full pytest with 1,217 passed and 10 skipped. For 0.7.35, `compileall` and the
available headless/regression/source-integrity suite completed with 734 passed and 4 skipped.
Three LAS round-trip scenarios were deselected because `lasio` is absent; Qt/pyqtgraph-dependent
files cannot be collected without `PySide6` and `pyqtgraph`. Ruff and mypy are not installed in
this container. The build remains a test build
until the full gate and Windows/HiDPI/PDF/physical-print matrix pass.

## Verified foundation

- safe LAS, CSV/TXT, Excel, and GeoScape/Paradox import;
- project format v16 with Semantic Channel Dictionary and Import Review;
- deterministic Report Passport schema v1;
- JSON/SVG golden fixtures for grids, legends, lithotypes, and annotations;
- shared screen/print geometry for grids, legend resolution, pattern identity, and annotations;
- synchronized RU/KK/EN documentation.

## 0.7.35 results

| Check | Result |
|---|---|
| Golden schema | `geoworkbench.render-golden/v1`, canonical JSON and SHA-256 |
| Grid | identical normalized fractions in screen px and print mm |
| Legend | shared order, deduplication, unknown fallback, and RU/KK/EN labels |
| Lithotypes | factory bitmap SHA-256 and physical tile size at 96 DPI |
| Annotations | shared box/leader/rotation/clipping contract |
| Visual | screen and print SVGs reproduce byte for byte |
| Focused golden-contract tests | 19 passed |
| Available regression | 734 passed, 4 skipped, 3 LAS scenarios deselected; Qt modules unavailable |
| Project format | v16 |

## Highest-risk remaining debt

- repeat the full Ruff/mypy/Qt/LAS gate;
- complete the Windows/HiDPI/PDF/physical-print smoke test;
- structural/SVG goldens do not replace platform raster comparison with tolerance;
- unify `ReportDefinition`, interval selection, and output fingerprinting.

## Next checkpoint

One shared `ReportDefinition` and interval selection for preview, PDF, and tabular export.

See [Golden rendering](GOLDEN_RENDERING.md), [Report Passport](REPORT_PASSPORT.md), and the
[engineering plan](../PROJECT_PLAN.md).
