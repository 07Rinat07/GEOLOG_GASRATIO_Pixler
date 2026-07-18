# User guide

GEOLOG GASRATIO@Pixler is an editor for drilling, mud-logging, and LAS data.

## Language

Choose Русский, Қазақша, or English on first launch. You can later change the language from
“Language / Язык / Тіл”. Restart the application to update every open window consistently.

## Import

Use “File → Import data...” (`Ctrl+I`) and select LAS, CSV/TXT, or Excel. Source files are
never modified. The CSV/TXT and Excel wizards use the selected language for index, DATE/TIME,
time-zone, preview, and validation controls.

## Table editing

The LAS table supports direct values, constant or noise interval fills, copy/paste, and
Undo/Redo. Every command and selection validation message uses the selected language.

## LAS export

The export dialog configures LAS 1.2/2.0, WRAP, NULL, precision, and custom-section
preservation. Settings, warnings, and overwrite confirmation use the selected language.

## Calculation formulas

Formula Profiles displays the passport, expression, output, source, and input-curve mapping.
DEXP names and descriptions are available in RU/KK/EN; formulas and units are not translated.

## Interval statistics

Visible interval statistics reports the point count, minimum, maximum, and mean for numeric
curves. Labels and messages are available in RU/KK/EN; source curve mnemonics and units remain
unchanged.

## Depth annotations

The editor adds, updates, and removes comments at a specified depth with Undo/Redo support.
The interface and project-tree node are available in RU/KK/EN; user-entered text is not
translated.

## Lithology intervals

The editor sets interval top, bottom, lithotype, and description and supports description
templates. The UI is available in RU/KK/EN; lithotype IDs and user descriptions remain
unchanged.

## Description templates

The editor stores reusable rock-description names and text in the project. Its interface is
available in RU/KK/EN; template content remains user-authored and is not translated automatically.

## Lithology legend

The legend lists symbols, codes, names, and lithotype IDs used in the current well. Its UI is
available in RU/KK/EN; codes, IDs, colors, and patterns remain identical across languages.

## Lithotype catalog

The catalog lists system and project rocks and creates project records with a code, RU/EN names,
category, color, and pattern. System records are protected from modification.

## Track Inspector

The inspector displays dataset, curve, or track details and configures width, linear or
logarithmic scale, and the X range. Labels are available in RU/KK/EN; model values are stable
and are not translated.

## Data and index information

Data Inspector provides the summary, indexes, curves, import diagnostics, LAS source profile,
and LAS header editor. All tabs and commands are available in RU/KK/EN; source diagnostics,
mnemonics, and values are not translated.

## Log display management

The log-display menu builds the default tracks, adds user-selected curves, and controls track
width, scale, range, order, and visibility. All commands are available in RU/KK/EN.

When a mixed LAS is opened, the general chart prioritizes a compatible gas-channel group
(`TG/TGAS`, `C1–C5`), so numeric lithology and zone codes do not compress the gas curves. Curves
use distinct colors and a legend. The log display shows one depth scale in metres in the Depth
track; adjacent tracks follow it synchronously without repeated axes. The default gas track uses
a logarithmic scale so Total Gas and minor components remain visible together; it can be changed
in the Track Inspector.

Each column supports an automatic X range or manually entered minimum and maximum values in the
Track Inspector. Switching to manual mode starts from the actual data range for that column. The
visible depth interval can also be entered numerically from the log-layout menu; “Show full depth
range” restores automatic full-depth display.

## Correcting depth order

The editor reports the depth direction and can safely create a new dataset with ascending depth.
The source LAS and source dataset are never modified.

## Basic Gas Ratios

The command calculates the unambiguous arithmetic ratios C1/C2, C1/C3, C2/C3, C1/(C2+C3),
and the `TG_CALC` sum of available components. The command and statuses are available in
RU/KK/EN; calculated-curve mnemonics are not translated.

## Normalized gas

In Formula Profiles, select “Drilling-normalized methane C1” and map C1, mud flow in gpm, ROP
in ft/h, and bit size in inches. The resulting `C1_NORM` curve is added to the dataset and shown
immediately; source curves are unchanged. See `docs/NORMALIZED_GAS.md` for the method passport.
Separate reference profiles create normalized C1–C5/isomer curves and `TG_NORM`; the engineer
must enter reference ROP, flow, bit diameter, and gas-system efficiency.

## DEXP, NCT, and overpressure indicators

Calculate `DEXP` and then `DEXPC` through Formula Profiles. The NCT command requests a normally
compacted shale calibration interval, creates `NCT` and `DEXPC_NCT`, and displays all three
curves. A negative deviation supports an overpressure hypothesis but must be checked against
lithology, drilling conditions, sensor quality, and other pressure-evaluation methods.

## Custom formulas

“Calculations → Custom formulas” creates and stores project formulas using curve mnemonics, for
example `100 * (C2 + C3) / (C1 + C2 + C3)`. Supported operations are `+`, `-`, `*`, `/`, power,
and `abs`, `sqrt`, `log10`, `minimum`, `maximum`. Source LAS curves cannot be overwritten.

## Engineer profile

Select “Engineer profile...” from the language menu. Multiple local profiles can store an
engineer name and organization; the active profile persists between application runs.

The complete engineering documentation currently lives in the parent `docs` directory and
is being migrated into synchronized RU/KK/EN user guides.

## Masterlog forms and symbols

The project format stores named forms with editable headers and column sets. The image manager now
provides built-in vector symbols, safe PNG/SVG import, thumbnails, renaming, and protected removal.
The depth-symbol editor selects a form column, point depth or interval, dimensions, and label with
Undo/Redo support. Points and stretched intervals print in the correct track and are clipped across
page segments by the independent millimetre renderer. Parameter anchors derive their X position
from the selected curve and the column's linear/log scale. Time anchors use a unique TIME/DEPTH
index pair and reject ambiguous depth matches. Page and free anchors will follow.

### Forms and independent headers

Open “Print → Masterlog forms” and select “From preset...”. Choose a field, gas-evaluation, or
geological preset and save it under a project-specific name. The application creates an independent
copy, so column, scale, or LAS mapping changes do not modify the built-in preset or another form.
Use “Header” and “Apply header preset...” to install an independently editable header copy.

### Mouse interval filling

In Masterlog preview, select “Fill lithology” or “Fill cuttings”. Hold the left mouse button and
drag from interval top to bottom. Choose one rock for lithology, or enter multiple cuttings
percentages whose total is exactly 100%. Overlapping intervals are rejected.

The saved composition is also available on the interactive log display. Use “Log display → Add
track → Cuttings” to add a 0–100% track. Component widths follow their percentages and use the
lithotype catalog color and pattern. The default layout adds this track automatically when samples
exist, and the synchronized cursor reports the sample composition.

### Interval calcimetry and LBA

In Masterlog preview, select “Calcimetry / LBA” and drag an interval with the left mouse button.
On the Calcimetry tab, enter the measured calcite `CaCO₃` and dolomite `CaMg(CO₃)₂`
fractions from 0 to 100%; their sum cannot exceed 100%. Once both are entered, insoluble residue
is calculated as `100 − Ca − Dol` and shown as the third part of the percentage bar. A blank field
means not measured, while an entered zero is a measured result.

On the LBA tab, record bitumoid group/type, intensity from 1 to 5, and fluorescence color/form.
When available, add solvent-cut type, speed and color, residue type/color, odour, stain and a
free-text description. On the Interpretation tab, the geologist records an interval conclusion;
it is stored separately from source observations. Lists remain editable for project-specific
classifications. Selecting exactly the same interval again loads the saved values for correction.

The sample results are stored in the project and included in Masterlog/PDF, point inspection and
the depth cursor. Add Calcimetry and LBA from “Log display → Add track”; the default layout adds
them automatically when data exists. The application records field/laboratory observations; it
does not replace instrument calibration or infer hydrocarbon saturation from fluorescence alone.
See [`docs/CALCIMETRY_LBA.md`](../CALCIMETRY_LBA.md) for method notes and sources.

“Print → Calcimetry and LBA interpretation...” opens the active-well summary and exports a
separate PDF report. It includes intervals, Ca/Dol/insoluble residue, every LBA field, and the
manual geologist interpretation in the current interface language.

### Stratigraphic intervals

Open “Edit → Stratigraphic intervals...”. For each interval, enter top, bottom, an editable rank,
required code, name, `#RRGGBB` color, and description. Intervals of the same rank cannot overlap;
different ranks may be nested, for example `System / Period → Series / Epoch → Stage / Age`.

You can also create an interval with the mouse: enable “Stratigraphy” in Masterlog preview and
drag from top to bottom. “Log display → Add track → Stratigraphy” adds one parallel lane per rank.
Point inspection and the synchronized cursor report every unit at the selected depth, and the
inspection can be pinned into PDF. See [`docs/STRATIGRAPHY.md`](../STRATIGRAPHY.md).

### Point inspection and PDF callouts

In “Inspect” mode, click a curve to see its column, nearest real sample, depth, value, unit, and
description. Lithology, cuttings, calcimetry and LBA clicks report interval top, bottom, results,
and description.
“Pin for PDF” adds the callout to preview, system printing, and PDF. “Callouts...” lists pinned
items and removes obsolete ones.

## Synchronized depth cursor

Select the red “Визирная линия” toolbar action or press `V`. A left click places one synchronized
horizontal line across every track; drag the line to move it. The “Cursor values” dock lists the
nearest actual sample depth and every unique curve value from visible tracks.

Use “Edit → Настроить визирную линию...” to select color and width. Color, width, and enabled state
are stored separately for the active engineer profile. Press the action or `V` again to restore
normal plot navigation.

The last cursor depth is stored in each dataset layout. Returning to a well restores that depth;
if the data range changed, it is safely clamped to the new limits. The values dock also reports
the current lithotype, interval top and bottom, and layer description.
