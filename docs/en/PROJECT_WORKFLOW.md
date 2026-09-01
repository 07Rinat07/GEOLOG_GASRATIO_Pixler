# Well project and daily LAS growth

## Core model

GEOLOG GASRATIO@Pixler uses a project-based workflow. The primary portable working document is the
`*.geologpkg` well project, not the source LAS, GS2, or Paradox DB file. Legacy
`*.geolog.json` projects remain readable and writable for compatibility.

| Object | Purpose |
|---|---|
| Source LAS/GS2/DB | Immutable measurement source |
| `*.geologpkg` project | All continuing work and source LAS revisions in one file |
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
- separate authored RU, KK, and EN text without one language overwriting another;
- the initial LAS and every successfully appended LAS with SHA-256, range, and provider details.

The recommended `.geologpkg` contains JSON, source LAS files, and images together and verifies
their checksums. A legacy project may create `<project name>.geolog.json.assets`; that directory
and its JSON file form one project set. A normal LAS
cannot fully retain forms, images, formatted descriptions, cuttings, LBA, or the other manual
layers.

## First working day

1. Import LAS, GS2, or Paradox DB and complete Import Review.
2. Select the tablet form.
3. Verify the well, active Dataset, axis, range, and critical curves.
4. Press **Ctrl+S** and choose a stable name such as `Well_101.geologpkg`.
5. Enter cuttings, LBA, calcimetry, descriptions, symbols, and intervals.
6. Press **Ctrl+S** again after material changes.

The GeoScape/Paradox **Open in editor** button only passes the Dataset to the project. It does not
mean that a LAS file has already been saved. For a direct `.db` import, **Save LAS** should open
the normal export dialog after the Dataset has been registered.

## Every following day

Do not open yesterday's LAS as a new well. Open the saved project and use
**File → Append daily LAS data...**:

1. select the same main Dataset in the current well;
2. select the local folder maintained by the server sync client, then choose today's LAS from the
   list; direct file selection remains available;
3. click **Analyze growth**;
4. review the range and the new/matching row counts;
5. click **Append**;
6. confirm that old manual layers remain and the new depth section appears;
7. save the project with **Ctrl+S**.

User-created, transferred, and locally calculated curves are not part of the required daily-LAS
schema. Their previous values are preserved, the new suffix is filled with missing values, and
calculated curves are marked for recalculation. Rerun and inspect them over the new range before
printing.

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

The application treats the synchronized folder as read-only. It records size, modification time,
and SHA-256 during analysis and verifies the file again immediately before append. A LAS that
changes during analysis or between analysis and selecting **Append** is rejected without changing
the Dataset. Wait for synchronization to finish, select the file again, and repeat
**Analyze growth**.

## Three languages in one project

Switch the application language and edit the same interval. Lithology, stratigraphy, cuttings
descriptions, LBA text, interpretations, and notes retain separate `ru`, `kk`, and `en` values.
Interval geometry, calcimetry numbers, cuttings composition, and curves are shared. For RU, KK,
or EN output, switch the language of the whole application, close any Print Centre that is already
open, and reopen **Print → Print and export center...**. Masterlog resolves the application-language
text from the same project. When a translation has not been entered, compatible saved text is
shown. No automatic machine translation occurs. Always check the authored-description language in
preview before delivery.

Do not bypass a conflict with ordinary import. Save the project, compare the sources, and then use
a separate controlled merge or correction workflow.

## Saving, backup, and transfer

The current release does not provide dependable automatic project saving. Do not rely on closing
the window: explicitly press **Ctrl+S** after import, daily growth, and manual entry.

The recommended layout separates synchronized LAS input from the working project and outputs:

```text
Well_101/
  incoming_las/
  project/Well_101.geologpkg
  backups/Well_101_YYYY-MM-DD.geologpkg
  exports/Well_101_YYYY-MM-DD_RU.pdf
```

Use `incoming_las` as read-only input. Keep one canonical working
`project/Well_101.geologpkg` so work is not accidentally continued in an old copy.

**Save project as...** writes a new path and makes that path the current working project. A dated
copy created with this command therefore becomes active. For a simple backup, it is safer to press
**Ctrl+S**, close the application, and copy the canonical file to `backups` with Windows tools.

For the new format, move or copy one file:

```text
Well_101.geologpkg
```

Do not edit the same synchronized `.geologpkg` concurrently on two computers: this is not
collaborative editing, and the last synchronized copy can overwrite the other. To transfer the
project, press **Ctrl+S**, close the application, and wait for one file to finish copying or
synchronizing. Open the `.geologpkg` on the other computer and verify the range, form, and one
entry in each language. For legacy `.geolog.json`, continue to copy `.assets` with the JSON. An
independent protected source archive is still recommended as a separate backup.

## LAS export

To send edited numeric curves to another application, use
**File → Export current dataset to LAS...**. Select LAS 1.2/2.0 settings and a new output path.
Export does not retain the project form, symbols, cuttings, LBA, or formatted descriptions and
does not replace **Ctrl+S**. A previously exported LAS is not updated automatically after later
edits; export it again.

## Current-release limitations

- A source LAS is intentionally never overwritten.
- The GS2 import path does not propagate its inner **Save LAS** action to the normal exporter;
  after GS2 import use the separate current-Dataset export command.
- Autosave and a separate Save Backup Copy command are not yet implemented.
- There is no command to roll back one committed daily append; use a dated `.geologpkg` copy.
- A large project stores curve arrays in JSON and can consume substantial disk space.

## Control check

At the end of a workday, save, close, and reopen the project. Check the old and new ranges, several
critical curves, one cuttings sample, LBA/calcimetry, a symbol, and the selected form. Only then
create the final LAS, PDF, or Masterlog output.
