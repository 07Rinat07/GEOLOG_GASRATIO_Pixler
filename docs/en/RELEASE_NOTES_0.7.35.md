# Release notes 0.7.35 — Golden Rendering Fixtures

Date: 23 July 2026. Status: test build.

## New

- four deterministic JSON golden fixtures for grids, legends, lithotype patterns, and
  annotations;
- composite SVG goldens for the screen tablet and printed Masterlog;
- every JSON uses `geoworkbench.render-golden/v1` and a canonical-payload SHA-256;
- `tools/update_render_goldens.py` reproduces committed fixtures byte for byte.

## Shared geometry

- major/minor grid geometry moved to Qt-independent `tablet/grid_geometry.py`;
- screen and print use the same normalized fractions;
- screen and Masterlog legends use shared `build_lithology_legend_from_ids()`;
- legacy lithotype pattern aliases resolve headlessly to exact factory bitmaps and content
  SHA-256;
- annotation boxes and leader endpoints use shared `annotation_layout.py` in px or mm;
- printed annotation leader endpoints now account for rotation.

## Verification

- 734 available headless/regression/source-integrity tests passed;
- 4 platform scenarios skipped;
- 3 LAS round-trip scenarios were deselected without `lasio`; Qt/pyqtgraph modules remain unavailable without `PySide6` and `pyqtgraph`;
- 19 focused golden-contract tests passed;
- `compileall` completed without errors;
- the full Ruff/mypy/Qt/LAS gate and Windows/HiDPI/PDF/physical-print smoke test must be
  repeated in the complete environment.

Project format remains v16.
