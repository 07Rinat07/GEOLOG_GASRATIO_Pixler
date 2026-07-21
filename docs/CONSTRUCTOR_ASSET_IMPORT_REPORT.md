# Constructor asset import report

Date: 21 July 2026

## Input

- `Litol_Bmp(2).zip`
- `Litol2_Bmp(2).zip`
- `Значки(2).zip`

## Result

- valid lithology source images: **297**;
- canonical lithology files after exact-file SHA-256 deduplication: **117**;
- unique decoded-pixel patterns: **115**;
- visually equivalent legacy groups intentionally retained separately: **2**;
- depth symbols: **19**;
- representative original BMP files retained in normalized stable-ID paths;
- tiled lithology previews use nearest-neighbour rendering;
- aliases from Russian, English, plural, singular, numeric, and legacy filenames are retained;
- legacy database/index files and `Thumbs.db` are not imported;
- corrected UI names are metadata only; original source filenames remain recorded in manifests.

## Integration status

The catalog is integrated directly into the full `GEOLOG_GASRATIO_Pixler` source tree.
Packaged resources live under `src/geoworkbench/resources/constructor_assets` and the
development copy is retained under `resources/constructor_assets` for validation and future
asset maintenance. The main menu, Constructor dialog, project installer, tablet pattern
resolver, header legend, depth-symbol editor and print renderer use these resources.

`FormManagerDialog` now debounces selection preview and rejects stale revisions. `TabletView`
handles wheel/touchpad navigation across plots, headers and empty areas. A Windows GUI smoke
test is still required because the build container does not provide PySide6 or pyqtgraph.
