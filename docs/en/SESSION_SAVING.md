# Saving imported and edited data

## Current-session information panel

The lower application bar continuously shows the project, well, active dataset, source file, and
**Saved / Modified** state. The panel tooltip contains the full source path, source format, row and
curve counts, project path, and the expected save target.

## Closing the application

When the working session contains unsaved changes, closing offers four actions:

1. **Save project** — preserves data, forms, presentation, intervals, and the other project
   objects in the primary `*.geologpkg` format; an open legacy `*.geolog.json` is written back for
   compatibility.
2. **Export LAS copy** — writes the current numeric curves and headers to a new LAS file.
3. **Don't save** — closes and discards the current session changes.
4. **Cancel** — returns to the application.

Original GeoScape, GeoScape II/GS2, and Paradox files are never overwritten automatically. Use a
project or a new LAS file for edited data. A source LAS also always opens a file-location dialog;
the suggested name follows the `original_edited.las` pattern.

## Finding a saved file

After a project or LAS file is saved successfully, the application shows the full path and offers
to open its folder. The first project save and **Save as…** always ask for a folder and name.
Regular **Ctrl+S** writes to the already selected project file.

LAS export does not replace project saving: LAS cannot retain forms, presentation, images,
cuttings, LBA, interpretation intervals, and other project layers.
