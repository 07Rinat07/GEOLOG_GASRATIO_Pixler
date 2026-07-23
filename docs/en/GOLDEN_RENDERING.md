# Deterministic render golden fixtures

## Purpose

Golden fixtures pin the shared screen-tablet and printed-Masterlog contract before manual
validation on a specific Qt/Windows device. They detect undeclared changes in geometry,
legend order, lithotype patterns, and annotation placement.

The fixtures contain no creation time, absolute path, random ID, or application version.
The same input contract always produces byte-identical JSON and SVG files.

## Contents

The committed fixtures live in `tests/golden_rendering`:

- `grid_screen_print_v1.json` — major/minor divisions, normalized fractions, screen px,
  and print mm coordinates;
- `legend_multilingual_v1.json` — order, deduplication, unknown fallback, and RU/KK/EN labels;
- `lithotype_patterns_v1.json` — compact/legacy aliases, factory asset SHA-256, bitmap tile
  dimensions, and physical size at 96 DPI;
- `annotations_screen_print_v1.json` — box, anchor, leader endpoint, rotation, and clipping
  for screen and print;
- `screen_tablet_v1.svg` and `print_masterlog_v1.svg` — composite visual goldens.

Every JSON document uses schema `geoworkbench.render-golden/v1` and stores the SHA-256 of
its canonical payload.

## Shared implementation boundaries

- `tablet/grid_geometry.py` is the Qt-independent source of major/minor geometry;
- the screen grid adapter and printed Masterlog use the same division contract;
- `build_lithology_legend_from_ids()` resolves code/name/color/pattern and unknown fallback
  consistently for screen and print;
- `lithology_pattern_catalog.py` resolves legacy aliases to exact factory bitmaps and
  validates content SHA-256 without Qt;
- `annotation_layout.py` converts reference pixels to screen px or print mm and computes
  the same box and leader endpoint, including rotation.

## Updating the goldens

```powershell
.\.venv\Scripts\python.exe tools\update_render_goldens.py
```

The command also works with an active interpreter: `python tools/update_render_goldens.py`.

A golden change is accepted only with an explanation of the intended rendering change.
`test_committed_render_goldens_match_deterministic_generator` compares every file byte for
byte, so accidental drift blocks the gate.

## Automated checks

The gate verifies committed/regenerated equality, JSON payload SHA-256, identical normalized
px/mm grid fractions, physical bitmap tile size, legend order/localization, annotation
96-DPI px-to-mm scaling, and the absence of machine-specific paths or timestamps.

Qt raster/PDF comparison with platform tolerance, HiDPI 100–200%, and physical printing
remain part of the mandatory Windows matrix before stable status.
