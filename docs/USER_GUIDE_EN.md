# GEOLOG GASRATIO@Pixler user guide

## 1. Interface order

The interface is organised by purpose:

- **permanent workspace tabs** — curves, LAS table, and tablet;
- **Tools** — the Files / PDF / Calculator window;
- **Print** — Print Centre and interpretation reports;
- **Help** — documentation, instructions, logs, and diagnostic bundles.

Utility windows open separately and no longer occupy permanent workspace tabs.

## 2. Files, PDF, and calculators

Open **Tools → Files / PDF / Calculator**.

1. Select a supported file and wait until it is fully loaded.
2. Before editing a PDF, verify the page and zoom level.
3. Save under a new name while the source file is still required.
4. Always check the units of calculator inputs.
5. Do not use results produced from blank, negative, or physically impossible values.
6. If PyMuPDF or Pillow is missing, the main application remains available and the window displays the installation command.

## 3. Print Centre

Open **Print → Print Centre**.

1. Verify the well, dataset, and selected interval.
2. Select paper, orientation, margins, scale, and print header.
3. Use A4 or A3 landscape orientation for wide charts.
4. Open preview and inspect every page.
5. Confirm that charts are not split, labels are readable, and the right axis remains within the printable area.
6. Save a control PDF first. Print physically only after reviewing that PDF.

A successful export does not guarantee correct layout. Always open and inspect the resulting file.

## 4. Interpretation reports

Open **Print → Interpretation reports**.

Available reports:

- **Mud-gas interpretation** — calculations, charts, prospective intervals, Excel, Word, PDF, and printing;
- **Calcimetry and LBA** — a separate interpretation report.

### Mud-gas report workflow

1. Select the well and dataset.
2. Check C1–C5, ROP, RPM, WOB, BIT/BS, and FLOW.
3. Select the normalised-gas source.
4. Configure BIT, ROP_REF, BIT_REF, FLOW_REF, and gas-system efficiency.
5. Recalculate the available curves.
6. Review DEXP quality and the reasons for gaps.
7. Refresh the report with charts.
8. Check scales, units, absolute C1–C5 values, and prospective intervals.
9. Save Excel or Word for table review.
10. Generate a PDF and inspect it from the first page to the last.

### Multi-page chart in PDF

PDF export and system printing use the same controlled multi-page renderer.

- the vertical scale is selected automatically from a standard series and printed on every chart sheet;
- a short well is printed on one chart sheet without artificial vertical stretching;
- a long well is divided into continuous, sequential depth ranges;
- every chart sheet repeats the left and right depth scales, outer borders, track headings, legend, and sheet range;
- curves remain vector graphics and are clipped only at the inner track boundaries;
- tables continue only between rows, and the table header repeats on continuation pages;
- the page number, title, legend, and note must remain inside the printable area.

Prospective intervals do not replace the geologist's conclusion.

## 5. Help and diagnostics

Open **Help → Documentation and instructions** for the built-in guide.

If an error occurs:

1. record the exact action sequence and time;
2. keep the source file and failed output;
3. open the log folder or create a diagnostic bundle;
4. do not repeat bulk exports until the cause is analysed;
5. provide the log, bundle, sample input, and a screenshot of the affected page to the developer.
