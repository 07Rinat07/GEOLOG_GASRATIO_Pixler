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

## 3. Files, PDF, and calculators

Open **Tools → Files / PDF / Calculator**.

1. Select a supported file and wait until it is fully loaded.
2. Before editing a PDF, verify the page and zoom level.
3. Save under a new name while the source file is still required.
4. Always check the units of calculator inputs.
5. Do not use results produced from blank, negative, or physically impossible values.
6. If PyMuPDF or Pillow is missing, the main application remains available and the window displays the installation command.

## 4. Cuttings log and rock descriptions in Interpretation

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

## 5. Print Centre

Open **Print → Print Centre**.

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

A successful export does not guarantee correct layout. Always open and inspect the resulting file.

## 6. Interpretation reports

Open **Print → Interpretation reports**.

Available reports:

- **Mud-gas interpretation** — calculations, charts, prospective intervals, Excel, Word, PDF, and printing;
- **Calcimetry and LBA** — a separate interpretation report.

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

## 7. Help and diagnostics

Open **Help → Documentation and instructions** for the built-in guide.

If an error occurs:

1. record the exact action sequence and time;
2. keep the source file and failed output;
3. open the log folder or create a diagnostic bundle;
4. do not repeat bulk exports until the cause is analysed;
5. provide the log, bundle, sample input, and a screenshot of the affected page to the developer.
