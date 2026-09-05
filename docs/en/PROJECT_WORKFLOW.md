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

The permanent lower panel shows **Source → Project file → Export**. It identifies the selected
read-only source, displays **Not saved** or the full path of the active `.geologpkg`, and treats
export as a separate LAS copy. The operator can therefore distinguish the input, the continuing
working file, and the external result at all times.

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
mean that a LAS file has already been saved. For a direct Paradox DB or GS2 import, **Save LAS**
opens the shared standard exporter only after the Dataset has been registered successfully.
Cancelling Import Review, closing the dialog, or encountering an error exports nothing.

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
7. wait for confirmation that the working `.geologpkg` was saved automatically and note the
   recovery-copy path for the previous revision.

If the project has not been saved yet, or a legacy `.geolog.json` is open, the application asks
for a working `.geologpkg` before changing the Dataset. Cancelling leaves the Dataset unchanged.
A successful append writes the new revision immediately; repeating an identical LAS remains a
no-op and creates no redundant backup.

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

After a material daily append, the working `.geologpkg` is saved automatically. Before replacement,
the application verifies that synchronization or another computer has not changed the file,
creates a self-contained recovery copy of the previous revision, checks the canonical file again,
and only then replaces it atomically. Continue to use **Ctrl+S** for ordinary manual editing. When
a dirty session is closed, the guard offers to save the project, export a LAS copy, close without
saving, or cancel.

The recommended layout separates synchronized LAS input from the working project and outputs:

```text
Well_101/
  incoming_las/
  project/Well_101.geologpkg
  project/.geolog-backups/...
  exports/Well_101_YYYY-MM-DD_RU.pdf
```

Use `incoming_las` as read-only input. Keep one canonical working
`project/Well_101.geologpkg` so work is not accidentally continued in an old copy.

**Save project as...** writes a new path and makes that path the current working project. A dated
copy created with this command therefore becomes active. Automatic recovery copies are stored
beside the canonical file in the managed `.geolog-backups` directory; the five newest verified
revisions are retained per project path. Do not rename its files or edit `index.v1.json`.

To restore an earlier revision, open the canonical project and choose
**File → Restore recovery copy...**. Select the revision and a new `.geologpkg` filename. The
canonical and active project are neither overwritten nor switched; save current work first, then
open the restored copy separately and compare it.

For the new format, move or copy one file:

```text
Well_101.geologpkg
```

Do not edit the same synchronized `.geologpkg` concurrently on two computers: this is not
collaborative editing. If the file changed after opening, the application blocks overwrite and
asks you to reopen the current file or save this session under a new name. To transfer the
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
- Autosave runs after a successful daily append; save ordinary manual edits with **Ctrl+S**.
- Recovery copies live beside the project, so also copy the closed `.geologpkg` to independent
  protected storage when organizational policy requires it.
- There is no command to roll back one committed daily append; use a dated `.geologpkg` copy.
- A large project stores curve arrays in JSON and can consume substantial disk space.
- Daily numeric append preserves existing geology but does not yet build new LAS rock-code
  intervals into already populated lithology and cuttings layers.
- Header details currently live in templates, rather than a shared well passport.
- The ready-description language selector chooses only the inserted text language. To save an
  authored RU/KK/EN version, switch the application language before opening the editor.

## Approved development model, 2026-09-05 — planned, not yet available

The following decisions are approved for development; they do not replace the current commands
above. WELL-01–WELL-06 stages and dependencies are tracked only in the
[project plan](../PROJECT_PLAN.md), with verifiable contracts in the [requirements](../REQUIREMENTS.md).

**One project and a shared passport (WELL-01).** Maintain a well in one canonical `.geologpkg`.
Depths, curves, interval geometry, rock percentages, and analyses are shared; descriptions,
interpretations, and comments have RU/KK/EN versions in the same record. Three languages do not
require three projects. The shared passport holds well details, logos, and construction, with
language variants where text needs translation. All forms use this passport. Migration preserves
identifiers and manual data; conflicting details in existing headers are presented for resolution
instead of silently choosing a value.

**Update well data (WELL-02).** The proposed workflow distinguishes a new depth section, late
analyses, and corrections to stored values. Preview lists added measurements, coded geology
intervals, missing-value fills, and conflicts. Changes retain provenance, and manual edits are
protected against silent replacement. Supplier codes are resolved through PROJ-09 source profiles
into a common rock catalog. Unknown codes require mapping rather than a guessed rock. Cancellation
retains the previous revision; applying the approved set creates a revision and recovery copy.
Affected calculations are rerun before issuing documents.

**Three-language editor and templates (WELL-03).** Each interval has Russian / Қазақша / English
tabs, initially following the application language. Selecting multiple multilingual templates
inserts matching fragments into all three versions. Block order, the template version at insertion,
and manual additions are retained. Later catalog changes do not rewrite finished descriptions.
Free authored text and its translations remain independently editable; machine translation is not
an already implemented feature.

**Translation readiness (WELL-04).** Each language field has missing, draft, reviewed, or stale
status. A translation retains its dependency on the original text revision. Editing the original
marks dependent translations for review without deleting them. New depths do not invalidate
translations in unrelated existing intervals.

**Linked forms (WELL-05).** One form has portrait and landscape layouts. The header, paper, and
tablet share one orientation; language controls captions and prepared text. Custom captions are
preserved per language. Orientation changes select a pair from the same custom header family;
a missing pair needs explicit configuration rather than an arbitrary substitute. Wrapping and
placement accommodate different translation lengths.

**Document package (WELL-06).** Select forms, languages, orientations, and a range: the entire well,
a new section, or a chosen interval. All outputs use the same saved revision. Readiness checks
identify missing data, stale translations, and calculations. Final documents must not silently
contain fallback text in another language; a working draft is allowed with an explicit mark.
Dated PDFs are immutable issue snapshots and do not change with subsequent project edits. At the
end of a day, the operator checks old and new sections, saves the project, completes only the
necessary translations, and issues the reviewed package.

## Control check

At the end of a workday, save, close, and reopen the project. Check the old and new ranges, several
critical curves, one cuttings sample, LBA/calcimetry, a symbol, and the selected form. Only then
create the final LAS, PDF, or Masterlog output.
