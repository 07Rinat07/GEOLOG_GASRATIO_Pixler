# GEOLOG GASRATIO@Pixler user guide

## 1. Interface order

The interface is organised by purpose:

- **permanent workspace tabs** — curves, LAS table, and tablet;
- **Tools** — the Files / PDF / Calculator window;
- **Print** — Print Centre and interpretation reports;
- **Help** — documentation, instructions, logs, and diagnostic bundles.

Utility windows open separately and no longer occupy permanent workspace tabs.

## 2. Quick data import

1. Choose **File → Import data...** (`Ctrl+I`).
2. Select a LAS, CSV/TXT, Excel, Paradox DB, or GS2 file directly. Its type is detected from the
   extension, so a separate format prompt is no longer needed.
3. A regular LAS opens in the safe compatible mode. Use **File → Advanced LAS import...** for
   strict or manual review modes.
4. Check the summary and channel list in the compact review. Expand index/NULL, manual mapping,
   technical columns, or the full warning list only when needed.
5. Select **Accept import**. Cancelling leaves both the project and source file unchanged.

## 3. Well project and daily LAS append

Keep continuing work in one `*.geologpkg` project. It stores the numeric curves, selected form,
cuttings log, lithology, LBA, calcimetry, intervals, images, comments, and separate RU, KK, and EN
texts. Source LAS files remain immutable inputs; regular LAS import or export does not replace
saving the project.

### Source → Project file → Export

The lower application panel continuously shows this working chain. **Source** is the selected
read-only LAS/GS2/DB input. **Project file** shows **Not saved** until the first `Ctrl+S`, then the
full path of the active `.geologpkg`. **Export** always creates a separate LAS copy; it does not
preserve the form, comments, or language text in place of the project.

For a direct Paradox DB or GS2 import, **Save LAS** first completes review and successful Dataset
registration, then opens the same standard LAS exporter. If Import Review is cancelled, the
dialog is closed, or import fails, export is not started and no file is created.

### Folder setup and the first working day

Use a clear folder structure and one stable working-project name for each well:

```text
Well_101/
  incoming_las/                  LAS files from the server-synchronised folder
  project/Well_101.geologpkg
  backups/                       dated copies of a closed project
  exports/                       PDF, LAS, and other deliverables
```

Treat `incoming_las` as input only. Wait for synchronisation to finish, do not edit a received LAS
manually, and never save the project over the source file.

1. Import the first LAS through **File → Import data...**, review the channels, and select
   **Accept import**.
2. Select the tablet form and verify the well, dataset, axis, and range.
3. Press `Ctrl+S` and save, for example, `project/Well_101.geologpkg`.
4. Fill intervals, geology, cuttings, LBA, calcimetry, symbols, and comments.
5. Enter Russian, Kazakh, and English versions of the text in the same project by switching the
   application language. Press `Ctrl+S` after each important block of work.
6. Close and reopen the `.geologpkg`; verify the form, old range, and one entry in every language.

### Daily LAS append without losing previous work

1. Open the existing `Well_101.geologpkg`; do not open yesterday's LAS as a new project.
2. Wait until the server client has completely synchronised today's LAS.
3. Open **File → Append daily LAS data...**.
4. Select the main dataset for the same well, then select the synchronised folder and LAS.
5. Select **Analyze growth**. Verify the current and incoming ranges and the counts of new and
   matching rows.
6. Select **Append** only when the result is expected. The existing dataset grows in place, so its
   forms, intervals, geology, comments, and three language versions remain attached.
7. Wait for confirmation that `.geologpkg` was saved automatically and that the previous revision
   has a recovery copy, then reopen the project and check both old and new intervals.

Curves created in the project, transferred from another dataset, or calculated locally do not
have to exist in the daily LAS. Their old values are preserved and their new rows remain empty.
After appending, rerun the required calculations and inspect the new interval before printing.

Possible analysis outcomes:

| Result | Required action |
|---|---|
| A new compatible suffix is present | Verify the range and select **Append**; the new `.geologpkg` revision is saved automatically |
| The same LAS or all rows already match | This is a safe repeat: there is nothing to append and the project is unchanged |
| Existing-depth, schema, unit, or well conflict | Append is rejected; do not bypass protection with regular import—save the project and investigate the source difference |
| The LAS changed during or after analysis | Wait for synchronisation to finish, select the file again, and repeat **Analyze growth** |

### Three languages, printing, versions, and transfer

Interval geometry, curves, numeric calcimetry, and cuttings composition are shared. Author text in
RU, KK, and EN is stored separately; switching language must not erase an existing translation.
There is no automatic machine translation. A saved compatible text may be shown when a
translation is missing, so verify every language manually before delivery.

To print RU, KK, and EN from one project, save the changes, switch the **application language**,
close any Print Centre window that is already open, and reopen **Print → Print and export
center...**. Inspect preview and use distinct names such as `Well_101_2026-08-31_RU.pdf`,
`_KK.pdf`, and `_EN.pdf`.

Keep only one canonical working file, `Well_101.geologpkg`. Before every successful daily append,
the application stores the previous revision in `.geolog-backups` and retains the five newest
verified copies. To restore one, use **File → Restore recovery copy...** and always select a new
`.geologpkg` filename.
Never edit the same synchronised `.geologpkg` on two computers at the same time. To transfer it,
save and close the project, wait for one complete copy or synchronisation, open that file on the
other computer, and verify the range, form, and RU/KK/EN text.

Daily append is saved automatically; use `Ctrl+S` for other important manual edits. If a modified
session is closed, the guard offers four actions: **Save project**, **Export LAS copy**,
**close without saving**, or **cancel closing**. LAS export does not mark the project as saved and
does not replace the first action.

See [Well project and daily LAS growth](en/PROJECT_WORKFLOW.md) for the complete workflow and
current limitations.

## 4. Files, PDF, and calculators

Open **Tools → Files / PDF / Calculator**.

1. Select a supported file and wait until it is fully loaded.
2. Before editing a PDF, verify the page and zoom level.
3. Save under a new name while the source file is still required.
4. Always check the units of calculator inputs.
5. Do not use results produced from blank, negative, or physically impossible values.
6. If PyMuPDF or Pillow is missing, the main application remains available and the window displays the installation command.

## 5. Cuttings log and rock descriptions in Interpretation

When LAS contains `КОД_ПОРОДЫ` or `ПОРОДА1_КОД`…`ПОРОДА5_КОД` channels, the application creates
lithology intervals and cuttings composition. A numeric code is not given an invented name: it gets
a neutral `Unidentified rock, code N` record. Use **Lithotype catalog → LAS rock codes** to read
codes from the current LAS, add a code, and select a confirmed lithotype. After applying, its name,
colour and pattern are used on screen, in MASTERLOG and in PDF. Mappings are saved in the project;
the source LAS is unchanged. **Reset** returns a code to its neutral record. Codes can be read again
after manual lithology or cuttings edits; existing intervals are not overwritten.

Use **Import dictionary** and **Export dictionary** in the same tab to exchange mappings
between projects. The portable JSON stores its schema version, source code, lithotype ID,
RU/KK/EN names, category, `#RRGGBB` colour, and pattern key. The catalog is project-wide;
independent source profiles are not available yet. Use separate projects for suppliers with
conflicting codes. Explicit JSON import replaces matching records; rereading LAS preserves
existing settings. Only the pattern key is transferred, not a custom image file.
The print-header catalog also includes **Masterlog header — A4 portrait** and **A4 landscape**.
They follow the supplied example: an empty customer logo slot on the left, BP Services on the right,
editable depths, dates, well and rig metadata, coordinates, geologists and engineers, lithology/LBA
legends, event symbols, and well construction. Double-click an element to edit it, drag to move it,
and save the result as a user header.
Edited numeric codes are used both in exported curves and the dictionary; duplicate codes
block export. A lithotype referenced by cuttings cannot be deleted.

### When LAS contains only the cuttings log

This is normal for files produced by different drilling programs. Do not re-import the LAS or
change the source file. Turn on **Select** mode (`Alt+1`) and fill the missing tracks:

1. In **Stratigraphy**, `Shift + left drag` the interval and choose its code/name.
2. In **Calcimetry** or **LBA**, drag the interval and choose **Fill calcimetry and LBA**.
   Edit the From and To depths manually; leave unknown fields empty.
3. In **Rock description**, drag an interval and enter text or select a template. It may overlap
   an imported cuttings interval.
4. Press **OK** after each interval and save the project with `Ctrl+S`.

These records do not rewrite LAS lithology or the cuttings log. Reopen the project and verify the
tablet, then open **Print → Print and export center** and preview the PDF: stratigraphy, rock
description, calcimetry, and LBA should appear in their own tracks.

When a new LAS is exported, manually entered lithology and cuttings are written to the numeric
`КОД_ПОРОДЫ`, `ПОРОДА1_КОД`…`ПОРОДА5_КОД` and `ПОРОДА1_КОЛИЧ`…`ПОРОДА5_КОЛИЧ` channels
when the lithotypes have numeric codes. Before ASCII data, the exported copy includes an ASCII-safe `~Other`
section carrying the `GEOWORKBENCH_ROCK_DICTIONARY` marker and the JSON dictionary contract.
The source LAS is unchanged; a colleague can use the sidecar JSON or extract the contract
from the exported copy in another program.

### Rename the displayed column

1. Open the tablet and enable **Edit form (F4)** or use the heading context menu.
2. Select the column whose system type is **Interpretation**.
3. Enter the required displayed title, for example **Cuttings log**.
4. Save the user form or project.

The same title is shown on screen and in print. The system type remains `INTERPRETATION`, so
saved projects and print templates remain compatible.

### Fill any description interval

1. Make sure **Select** mode (`Alt+1`) is active.
2. Hold `Shift` in an Interpretation or Rock description track.
3. Left-drag from the interval top to bottom and release the mouse button.
4. Correct the exact **From, m** and **To, m** values in the dialog.
5. Select the ready-description language: Russian, Kazakh, or English.
6. Select a ready rock template or enter arbitrary text. Use **Text alignment** to select left,
   centre, or right. **Wrap words** is enabled by default; clear it when automatic wrapping is not
   wanted. Rock percentages are not required for this workflow.
   You can select any number of ready templates in succession; each new template is appended
   instead of replacing the existing description.
7. Press **OK**, then save the project with `Ctrl+S`.

The saved text appears immediately in the selected interval and is included in Masterlog, PDF,
and printing. With **Wrap words** enabled, words wrap automatically. Every track-width change
recalculates wrapping, font size, and shortening against the actual visible width. If space is
limited, the screen and print font shrink;
if the complete text still cannot fit at the safe minimum, the tablet shows an ellipsised preview.
Zooming in restores the complete text automatically. Text is never painted above the top or below
the bottom of its interval, while the complete original remains stored in the project.
Double-click the description to reopen it. **Delete description** removes only the
text; composition, LBA, and calcimetry remain intact. Existing system interpretation intervals
are not deleted and remain visible outside an overlapping description.

### Description from the shared sample editor

In Cuttings, Calcimetry, and LBA tracks, `Shift + left drag` opens the shared sample editor. It
accepts up to four rocks totalling `100%`, analyses, a ready template, and a description. After
saving, the same description automatically appears in the Interpretation column.
The description tab supports repeated insertion: choose ready templates one after another and
each one is appended to the description already assembled.

When LAS already contains cuttings intervals, fill an analysis independently: use
`Shift + left drag` in the Calcimetry or LBA column and choose **Fill calcimetry and LBA**.
The From and To depths are editable in the dialog. The analysis is stored as its own interval
without changing the imported LAS composition. In the Rock description column you can likewise
drag an interval over the cuttings log; overlap with an imported sample no longer blocks the description.

## 6. Print Centre

Open **Print → Print and export center...**.

1. Verify the well, dataset, and selected interval.
2. Select paper, orientation, margins, scale, and print header.
3. Use A4 or A3 landscape orientation for wide charts.
4. Open preview and inspect every page.
5. Confirm that charts are not split, labels are readable, and the right axis remains within the printable area.
6. Save a control PDF first. Print physically only after reviewing that PDF.

In the factory **MASTERLOG — A4 landscape** and **MASTERLOG — A4 portrait** forms, the
`INTERPRETATION` description column is displayed as **Rock description**. The portrait widths are
already reduced so this column fits on one A4 sheet. This does not replace the percentage
cuttings-composition column: description text and percentages remain separate data. The depth
column is widened so four-digit depth labels remain readable.

When Russian, Kazakh, or English is selected, built-in form names, columns, parameters, gas-axis
labels, and print-header fields are shown in that language. The active log display refreshes
immediately; reopen a modal Library or Constructor window if necessary. Known factory captions in
an existing form are also translated without recreating it, while arbitrary custom titles remain
unchanged. ROP, WOB, SPP, C1–C5 mnemonics, chemical formulas, and units remain international.

To create another language version, close the open Print Centre, switch the language of the whole
application, and reopen **Print → Print and export center...**. Then verify the author-description
language in preview; changing the interface language alone does not create a missing translation.

A successful export does not guarantee correct layout. Always open and inspect the resulting file.

## 7. Interpretation reports

OPUS Gasomer section headings, classes, QC states and the missing-LOD message follow the
selected RU/KK/EN language. Formulas, technical identifiers and original references remain
unchanged. Full technical evidence may still contain English text.
PDF interval headings stay with their descriptions, and column widths are passed explicitly
to Qt; long tables still require a readability check before release.

Open **Print → Interpretation reports**.

Available reports:

- **Mud-gas interpretation** — calculations, charts, prospective intervals, Excel, Word, PDF, and printing;
- **Full geological report** — one-metre and actual-sample rocks, stratigraphy, calcimetry,
  interval gas statistics, and detailed LBA. The component sum is calculated independently and
  does not substitute for missing `Total Gas`.

### Mud-gas report workflow

The left panel shows the primary route: **1. configure inputs → 2. calculate curves →
3. review the report → 4. print and export**. Step 4 opens the prepared report and focuses the
PDF/Word/Excel/print actions; **Instructions** opens the detailed methodology.

1. Select the well and dataset.
2. Check C1–C5, ROP, RPM, WOB, BIT/BS, and FLOW.
3. Select the normalised-gas source.
4. Configure BIT, ROP_REF, BIT_REF, FLOW_REF, and gas-system efficiency.
5. Recalculate the available curves.
6. Review DEXP quality and the reasons for gaps.
7. Refresh the report with charts.
8. Check scales, units, absolute C1–C5 values, and prospective intervals.
9. Save Excel or Word for table review.
10. Complete the cover-page details before PDF export or physical printing.
11. Generate a PDF and inspect it from the first page to the last.

For the integrated gas deliverable, apply **Integrated C1–C5 gas log**. Its order is depth/ROP,
C1–nC5, Total Gas, normalized and relative composition, Wetness/Balance/Character with isomer
ratios, and Pixler. On the final page the graph must end before the repeated lower header; no
curve may continue below it.

In **C1–C5 components**, the numeric X scale is hidden by default so seven components do not
overload the header. Each C1–C5 curve remains linear and keeps its own automatic range. To show
the numbers and engineering ruler, select the column and enable **Track Inspector → Track and
scale → Show numeric X scale**. **Vertical grid** is independent, so the scale can be enabled
without a grid. After changing it, save the user form, regenerate the PDF, and inspect the header
on every page. Forms saved before the upgrade keep the numeric scale visible and do not change
their appearance.
If a separate numeric depth is needed before the components, first create a user copy of the
factory form and enable the hidden repeat depth column in the structure editor. Column visibility
is editable, while its depth track remains protected against accidental replacement.

### Editable cover-page details

A separate form opens before PDF export and physical printing. It allows manual editing of:

- report title and subtitle;
- project and well;
- field or area and location;
- operator/client and service company;
- rig or unit;
- dataset label and report interval;
- document number, revision, status, and date;
- Prepared by, Checked by, and Approved by fields;
- classification and cover note.

Application values are used only as initial suggestions. Manual values affect the PDF and printing but do not rename the project, well, or loaded files inside the application. Use **Restore application values** to restore the original suggestions. Values entered for the current dataset remain available until the application is closed or a different dataset is selected.

### Multi-page chart in PDF

PDF export and system printing use the same controlled multi-page renderer.

- the first page is an independent industry-style cover with document-control and sign-off blocks;
- the vertical scale is selected automatically from a standard series and printed on every chart sheet;
- major depth ticks use stronger lines and numeric labels on both the left and right axes;
- shorter intermediate ticks and a supporting horizontal grid are printed between major ticks;
- numeric-label spacing becomes finer for short intervals and coarser for long intervals so numbers do not overlap;
- a short well is printed on one chart sheet without artificial vertical stretching;
- a long well is divided into continuous, sequential depth ranges;
- every chart sheet repeats the left and right depth scales, outer borders, track headings, legend, and sheet range;
- curves remain vector graphics and are clipped only at the inner track boundaries;
- tables continue only between rows, and the table header repeats on continuation pages;
- the page number, title, legend, and note must remain inside the printable area.

### Printing to a physical Windows printer

1. Start report printing and complete or edit the cover-page details.
2. Select **portrait** or **landscape** orientation.
3. Select **first page to last page** or **last page to first page**. First-to-last is the default.
4. In the native Windows dialog, select the Epson printer, page range, copy count, and driver properties.
5. Selecting a range of **1–2** sends only pages 1 and 2 in the selected order.
6. A progress dialog is shown while pages are prepared. **Stop** prevents pages that have not yet been sent from being transferred.
7. Pages already placed in the Windows spooler or printer buffer may still need to be cancelled from the system print queue.
8. After starting the job, check the application message showing how many pages were sent to the queue.

Prospective intervals do not replace the geologist's conclusion.

## 8. Help and diagnostics

Open **Help → Documentation and instructions** for the built-in guide.

If an error occurs:

1. record the exact action sequence and time;
2. keep the source file and failed output;
3. open the log folder or create a diagnostic bundle;
4. do not repeat bulk exports until the cause is analysed;
5. provide the log, bundle, sample input, and a screenshot of the affected page to the developer.

For a daily-append problem, also include the `.geologpkg` path, target dataset name, LAS name,
synchronisation completion time, and the **Analyze growth** result. A diagnostic bundle is not a
backup of the project or source LAS.
