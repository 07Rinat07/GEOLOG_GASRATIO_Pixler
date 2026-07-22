# Release notes 0.7.18

## Tablet-wide annotation overlay

- Callouts, comments, images and saved curve values now use one top-level overlay spanning the complete tablet workspace instead of individual track scenes.
- The text box can be dragged across column boundaries while the depth/time/curve anchor remains attached to source data.
- A selected object exposes eight resize handles: four corners and four sides.
- Single-click selects; drag moves; double-click/F2/Enter edits; Delete removes; right-click opens the object menu.
- The compact F4 toolbar includes Edit selected and Delete selected actions.
- Annotations no longer clutter the project/settings tree; the separate “All…” manager remains available.
- The same overlay is included in track capture, PDF and print output.

## Responsive DB → LAS import

- Binary reading and Dataset construction remain in worker threads, while preview tables are populated in short Qt timer slices.
- Expensive per-cell automatic column-width calculation was removed from the population path.
- The dialog adapts to the available screen, retains a system close button, keeps Cancel/Close visible and performs safe cancellation.
- One six-stage scale reports header, schema, records, analysis, preview and document creation.
- The current file, processed counts, elapsed time and a slow-operation hint are visible.
- Closing during reading requests cancellation and waits for a safe block boundary without modifying the source DB.

## Validation

- 128 focused non-GUI tests passed.
- `compileall` completed successfully.
- `BLData(1).db`: 3,488 records, 70 fields, about 0.28 s read time; actual S113 step is 0.4 m.
- `D250(1).db`: 1,739 records, 101 fields; multiple depth candidates still require confirmation.
- Source DB/PX/TV/FAM files remained unchanged.

A full interactive Windows Qt smoke test remains mandatory because PySide6 and pyqtgraph are unavailable in the build container.
