# Well project and daily LAS growth

## Core model

GEOLOG GASRATIO@Pixler uses a project-based workflow. The primary working document is the
`*.geolog.json` well project, not the source LAS, GS2, or Paradox DB file.

| Object | Purpose |
|---|---|
| Source LAS/GS2/DB | Immutable measurement source |
| `*.geolog.json` project | All continuing work for the well |
| Exported LAS | Separate copy of current numeric curves for another application |
| PDF/Masterlog | Final presentation and print output |

Opening or importing a LAS creates a Dataset in the current session but does not create a new LAS
on disk. After the first import the project is still unsaved; the main-window title shows this with
an asterisk (`*`).

## What the project stores

Pressing **Ctrl+S** writes the following to the project:

- wells, datasets, depth/time indexes, headers, and all curve values;
- table and pencil edits, calculated curves, and daily-growth history;
- selected form, tracks, scales, and screen layout;
- lithology, stratigraphy, cuttings plots, and sample descriptions;
- LBA, calcite, dolomite, and interpretations;
- symbols, images, comments, callouts, and saved curve values;
- interpretation intervals, events, and project catalogs.

A `<project name>.geolog.json.assets` directory may be created next to the project for source LAS
artifacts and inserted images. The JSON file and this directory form one project set. A normal LAS
cannot fully retain forms, images, formatted descriptions, cuttings, LBA, or the other manual
layers.

## First working day

1. Import LAS, GS2, or Paradox DB and complete Import Review.
2. Select the tablet form.
3. Verify the well, active Dataset, axis, range, and critical curves.
4. Press **Ctrl+S** and choose a stable name such as `Well_101.geolog.json`.
5. Enter cuttings, LBA, calcimetry, descriptions, symbols, and intervals.
6. Press **Ctrl+S** again after material changes.

The GeoScape/Paradox **Open in editor** button only passes the Dataset to the project. It does not
mean that a LAS file has already been saved. For a direct `.db` import, **Save LAS** should open
the normal export dialog after the Dataset has been registered.

## Every following day

Do not open yesterday's LAS as a new well. Open the saved project and use
**File → Daily LAS growth…**:

1. select the same main Dataset in the current well;
2. select today's LAS;
3. click **Analyze growth**;
4. review the range and the new/matching row counts;
5. click **Append**;
6. confirm that old manual layers remain and the new depth section appears;
7. save the project with **Ctrl+S**.

The command mutates the selected Dataset in place. Its identifier does not change, so its form,
cuttings, LBA, calcimetry, intervals, and Dataset-scoped symbols remain associated. Both a
cumulative LAS with an identical old range and a file containing only the new suffix beyond the
last depth are supported.

## Compatibility and conflict rules

Daily growth is a strict append-only operation:

- DEPTH cannot be appended to a TIME Dataset or vice versa;
- well name, index type, and index unit must be compatible;
- curve mnemonic sets and curve units must match;
- depth/time direction must match;
- identical overlap is skipped;
- a changed value at an already stored depth is a conflict;
- reimporting the same SHA-256 is a safe no-op.

Do not bypass a conflict with ordinary import. Save the project, compare the sources, and then use
a separate controlled merge or correction workflow.

## Saving, backup, and transfer

The current release does not provide dependable automatic project saving. Do not rely on closing
the window: explicitly press **Ctrl+S** after import, daily growth, and manual entry.

**Save project as…** writes a new path and makes that path the current working project. A dated
backup can be created under a new name, after which work continues in that new version. Before
copying the project with Windows tools, press **Ctrl+S** first.

Move or copy these items together:

```text
Well_101.geolog.json
Well_101.geolog.json.assets\
```

If no `.assets` directory exists, the JSON file is sufficient. Keep daily input LAS/GS2/DB files
in a separate protected archive as well: append history records name, SHA-256, and range, but does
not replace a full archive of every source file.

## LAS export

To send edited numeric curves to another application, use
**File → Export current Dataset to LAS…**. Select LAS 1.2/2.0 settings and a new output path.
Export does not retain the project form, symbols, cuttings, LBA, or formatted descriptions and
does not replace **Ctrl+S**. A previously exported LAS is not updated automatically after later
edits; export it again.

## Current-release limitations

- A source LAS is intentionally never overwritten.
- The GS2 import path does not propagate its inner **Save LAS** action to the normal exporter;
  after GS2 import use the separate current-Dataset export command.
- Autosave, a separate Save Backup Copy command, and one portable ZIP project package are not yet
  implemented.
- A large project stores curve arrays in JSON and can consume substantial disk space.

## Control check

At the end of a workday, save, close, and reopen the project. Check the old and new ranges, several
critical curves, one cuttings sample, LBA/calcimetry, a symbol, and the selected form. Only then
create the final LAS, PDF, or Masterlog output.
