# GEOLOG GASRATIO@Pixler 0.7.92

## Compact tablet captions

- Long special-column captions such as **Stratigraphy** and **Cuttings log** are rendered as one rotated line and automatically fitted to the available header rectangle instead of being clipped.
- The rotated tablet-title band was increased from 88 to 96 px to keep long localized captions readable on Windows font/DPI combinations.
- **LBA** now remains horizontal by default in all factory forms, new tracks, migrated user forms, and saved tablet layouts because its three-letter caption does not require rotation.
- Depth/Time, Stratigraphy, Lithology, Cuttings log and Calcimetry keep the compact vertical default.

## Persistence

- Project format remains `v21`.
- Form schema is `v11`.
- Tablet layout is `v21`.
- Forms/layouts from 0.7.91 are migrated automatically; the LBA orientation is corrected during loading.

## Validation

- Canonical startup remains `python -m geoworkbench.app.main`.
- Source compilation and documentation audit are part of the release gate.
- Focused compact-column, form migration, tablet layout and version tests are included.
