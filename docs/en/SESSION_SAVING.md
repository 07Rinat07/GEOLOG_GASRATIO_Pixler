# Saving imported and edited data

## Current-session information panel

The lower application bar continuously shows **Source → Project file → Export**, together with
the well, active dataset, and **Saved / Modified** state. The source remains read-only. Before the
first save, the project field says **Not saved**; afterwards it shows the full path of the active
`.geologpkg`. The export field identifies LAS as a separate copy. The panel tooltip adds the full
source path, format, and row and curve counts.

## Save LAS after Paradox and GS2 import

For a direct Paradox DB or GS2 import, **Save LAS** opens the shared standard exporter only after
the Dataset has passed review and registered successfully. Cancelling Import Review, closing the
dialog, or encountering an error does not start export or create a partial file. **Ctrl+S** saves
the complete project, not the LAS copy.

## Closing the application

When the working session contains unsaved changes, the close guard offers four actions:

1. **Save project** — preserves data, forms, presentation, intervals, and the other project
   objects in the primary `*.geologpkg` format; an open legacy `*.geolog.json` is written back for
   compatibility.
2. **Export LAS copy** — writes the current numeric curves and headers to a new LAS file.
3. **Don't save** — closes and discards the current session changes.
4. **Cancel** — returns to the application.

Daily growth is a separate protected material operation: a working `.geologpkg` is required before
the Dataset changes; after a successful append the new revision is saved automatically and the
previous one is stored in `.geolog-backups`. Repeating an identical LAS writes nothing. Continue
to save ordinary manual edits with **Ctrl+S**.

If synchronization changes the project after it was opened, overwrite is blocked. Save the current
session under a new name or reopen the current file. A verified earlier revision can be restored
with **File → Restore recovery copy...** only to a new `.geologpkg`; the active file is not
overwritten.

Original GeoScape, GeoScape II/GS2, and Paradox files are never overwritten automatically. Use a
project or a new LAS file for edited data. A source LAS also always opens a file-location dialog;
the suggested name follows the `original_edited.las` pattern.

## Finding a saved file

After a project or LAS file is saved successfully, the application shows the full path and offers
to open its folder. The first project save and **Save as…** always ask for a folder and name.
Regular **Ctrl+S** writes to the already selected project file.

LAS export does not replace project saving: LAS cannot retain forms, presentation, images,
cuttings, LBA, interpretation intervals, and other project layers.
