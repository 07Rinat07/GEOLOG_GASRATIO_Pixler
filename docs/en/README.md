# User guide

> **0.7.6:** a separate **Editor** section and **LAS Editor** button (`Ctrl+Alt+E`) combine creation, table editing, descending-depth repair, resampling, curve insertion and splicing. Results are saved as new LAS files without overwriting sources. See the [LAS Editor guide](LAS_EDITOR.md).


GEOLOG GASRATIO@Pixler is an editor for drilling, mud-logging, and LAS data.

- a ready A3 KazGeology Masterlog template with two uploadable logos and coloured scales;

## Language

Choose Русский, Қазақша, or English on first launch. You can later change the language from
“Language / Язык / Тіл”. The selected language is applied immediately to the entire open interface; no application restart is required.

## Import

Use “File → Import data...” (`Ctrl+I`) and select LAS, CSV/TXT, or Excel. Source files are
never modified. The CSV/TXT and Excel wizards use the selected language for index, DATE/TIME,
time-zone, preview, and validation controls.

## Table editing

The LAS table supports direct values, constant or noise interval fills, copy/paste, and
Undo/Redo. Every command and selection validation message uses the selected language.
Small values are displayed and opened for editing in plain decimal notation, for example
`0.000052` instead of `5.2e-05`. To format particular columns, select cells in them and click
“Number format...”. Adaptive decimal, fixed decimal places, and scientific modes include a
live preview. The mnemonic-based setting is stored separately for the active engineer profile.
It changes display only: editing opens the full decimal value, CSV keeps full precision, and
Excel keeps both the numeric type and its cell format.

## Automatic LAS parameter mapping

LAS column order does not carry semantic meaning. The application resolves base parameters from
the original and canonical mnemonic, the Sensors catalog, description, chemical formula, and
unit. Common variants such as `C1/С1/CH4/METHANE`, `C2/C2H6/ETHANE`, and
`C3/C3H8/PROPANE`, C4–C5 components, Total Gas, drilling, mud, and basic petrophysical curves
are supported. Equally confident duplicate channels are reported as ambiguous rather than chosen
at random. Gas Ratio converts `%`, `ppm`, `ppb`, and fractions to a compatible scale. See
[LAS parameter recognition](LAS_PARAMETER_RESOLUTION.md).


## GeoData depth workspace

The form manager includes one coherent depth workspace grouped into Geology, Technology, and Gas
data. Every track uses one depth coordinate and one parameter-header height. Lithology is created
with `Shift + left drag` and reopened by double-clicking. Cuttings, LBA, Calcimetry, and rich
description are stored as one shared sample and refresh together. The gas section separates
absolute composition `TG_CALC`, `C1`, `C2` from relative component composition
`C1_REL`–`C5_REL`; a fully missing sample remains `NULL/NaN`. See
[GeoData depth workspace](GEODATA_DEPTH_WORKSPACE.md).

## Geological-geochemical Masterlog

The factory “Geological-geochemical Masterlog” follows the supplied working reference: 
stratigraphy, WOB/ROP/DMC/D-exponent, depth, cuttings diagram, LBA, calcimetry, lithology,
C1–C5/Total Gas, and rock descriptions. The factory form is protected; an editable user copy
preserves column order, widths, captions, bindings, scales, and styles. The screen form is linked
to the `geological_geochemical` print header.

Calcimetry displays calcite CaCO₃, dolomite CaMg(CO₃)₂, and the calculated insoluble residue for
each sample interval. A measured `0` remains zero, while a missing value is not drawn. LBA uses
interval symbols for bitumen type and intensity 1–5, while the complete observation remains in
the tooltip and project data. For ordinary curves, LAS NULL/NaN breaks the line, so points on
opposite sides of a missing interval are never connected.

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

A vertical-navigation bar is shown above the tablet. The “Vertical axis” list can select a
recognized MD/TVD/TVDSS depth index or a TIME/DATETIME index. Every track switches together:
curves, lithology, stratigraphy, interpretation intervals, and cuttings remain aligned through the
row-wise TIME↔DEPTH relationship.

The wheel scrolls the selected axis, `Ctrl+wheel` changes vertical zoom, and dragging pans. An
explicit vertical scrollbar is available on the right; `+` and `−` change zoom and “Full range”
restores the complete interval. “Go to” accepts a depth/numeric time value or an ISO timestamp such
as `2026-07-18 12:30:00` for DATETIME indexes. Navigation is clamped to the actual bounds of the
selected index.

Each column supports an automatic X range or manually entered minimum and maximum values in the
Track Inspector. Switching to manual mode starts from the actual data range for that column. A newly opened depth form starts with an exact **50 m** window; a range already saved in the project is restored without reset. The
“Visible interval” control defines how many vertical-axis units are shown at once: `1`, `5`, `10`,
`20`, `30`, `40`, `50`, `60`, `70`, `80`, `90`, `100`, or a custom value. A selection is applied
immediately to every track. A manually typed number applies automatically without Enter. The label
shows the current boundaries and actual span, for example `100–150 · span 50 m`. Time forms use the
unit of the selected TIME index. “Full range” restores the complete interval.

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

“Columns...” adds, edits, reorders, and removes form columns. In preview, double-click a column
header to change that column's title, type, width, scale, range, and plotted curve set directly.
“Choose from LAS...” lists parameters from the active file. When the form keeps standard parameter
names but an external LAS uses vendor names, use “Map LAS curves...”; the mapping belongs to that
form and dataset and does not alter the source LAS. Form edits are included in the next project save,
and package export transfers an individual form.
The built-in Field Masterlog follows the reference field order: drilling, depth, core/slide,
cuttings, direct/cut fluorescence, ILM/ILD, C1–C5 gas, calcimetry, lithology, interpretation,
and free-text description. Every column remains editable or removable for a project.
Select “Curve styles...” in a graphical column to configure each mnemonic's `#RRGGBB` color,
width, solid/dash/dot line, and optional individual X range. Without an individual range, the
column range remains the fallback. The printed header shows each mnemonic and range in its curve
color.
The same dialog independently enables vertical and horizontal engineering grids and configures
major divisions, minor subdivisions within each major interval, and line opacity. Graphical columns
in the built-in field presets include a grid by default. Existing forms keep it disabled until it is
enabled in column properties; the settings are stored with the form and applied to PDF output.
The Header editor also offers a dynamic `lithology_legend` element. It prints each rock's color,
pattern, code, and localized name automatically. Select either the full catalog or only lithotypes
used by lithology and cuttings within the printed interval, configure the column count, and optionally
hide codes. New Field Masterlog and Geological Description presets include the expanded full-catalog
header. System and project lithotypes use the same rendering without modifying the source catalog.

### Mouse interval filling

In Masterlog preview, select “Fill lithology” or “Fill cuttings”. Hold the left mouse button and
drag from interval top to bottom. Choose one rock for lithology, or enter multiple cuttings
percentages whose total is exactly 100%. Overlapping intervals are rejected.

“Cuttings description” selects an interval in the same way and opens a normal multiline text field.
The text is stored with the cuttings sample and prints in a `cuttings_description` column. Composition
and description may be entered in either order.

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

## Interpretation intervals

Open “Edit → Interpretation intervals...”. Each well may contain multiple named interpretations,
such as “Primary”, “Alternative”, or “Post-log review”. Every interval stores top, bottom, type,
label, `#RRGGBB` color, and comment. Intervals of the same type cannot overlap, while different
types may intentionally overlay the same depth, for example “Reservoir” and “Risk”. Bounds are
validated against the active dataset.

Creating, updating, and deleting interpretations or intervals supports Undo/Redo. Data is persisted
inside the project as `Project → Well → Interpretation → Intervals`; the source LAS is never
modified. The active interpretation can be exported to JSON, CSV, or Excel. JSON retains
interpretation metadata and the well name, CSV contains a flat interval table, and Excel adds a
separate Metadata sheet.

The active interpretation is rendered as a dedicated tablet track. Each interval type receives its
own lane, so overlapping intervals of different types remain distinguishable. Clicking a painted
interval performs lane-and-depth hit testing, selects the same row in the manager, and opens the
property panel. The panel edits top, bottom, type, label, color, and a multiline comment through the
same validation and Undo/Redo history. Double-clicking an interval in the project tree opens the
corresponding tablet selection. Active intervals are also included in the cursor summary. Switching
wells automatically clears stale selection so properties cannot leak across wells.

## LAS curve selection and tablet building

After a LAS file is loaded, the dockable “LAS curves” panel opens. It lists each curve's mnemonic,
unit, parameter group, finite-value coverage, actual range, and description. Search covers all of
those fields. Channels without numeric data are disabled and clearly marked.

“Select recommended” chooses a practical working set, while “Build tablet from selected” creates a
readable layout based on physically compatible parameter families. Gas components and `DEXP/NCT`
are compared together, while `ROP`, `RPM`, `WOB`, torque, pressure, flow, mud density, temperature,
GR, resistivity, and other incompatible quantities receive independent scales. Selected curves can
also be added as a new track or assigned to the currently selected graph track. The tablet uses a
light plotting surface, units in legends, and a robust automatic X range that is not stretched by a
single outlier.

## Sensors reference and direct interval editing

After LAS import, the “LAS curves” panel shows the original and canonical mnemonic, unit,
parameter group, finite-value coverage, actual range, catalog reference range, and description.
The normalized Sensors reference recognizes common aliases such as `TGAS → TG`, `CH4 → C1`, and
`BIT_RPM → RPM`. It does not rename the source LAS curve or alter its values.

“Edit → Sensors and mnemonic reference...” opens the complete searchable catalog. “Connect
external JSON...” activates another schema-v1 reference for the current run. Invalid schemas,
categories, colors, or ranges are rejected before activation.

Use the Tablet toolbar or menu to edit interpretation intervals directly:

- `Alt+1` — select an existing interval;
- `Alt+2` — draw by dragging from top to bottom;
- `Alt+3` — drag the top or bottom boundary.

Depths snap to the nearest sample in the active LAS dataset. A translucent dashed preview is shown
while dragging, and `Esc` cancels an unfinished gesture. On release, dataset bounds and same-type
overlap rules are validated. Use `Ctrl+Alt+Z` to undo and `Ctrl+Alt+Shift+Z` to redo a completed
change. Edit the exact label, type, color, and comment in the property panel.

## Trainable user mnemonic dictionary

Use “Edit → Sensors and mnemonic reference...” to create mapping rules for LAS files received from other vendors. A rule stores the foreign mnemonic, the application's canonical mnemonic, parameter name, unit, category, compatible track family, aliases, and recommended range. User rules persist between application runs, override the built-in Sensors catalog, and are applied automatically to subsequent LAS files. The dictionary can be imported from or exported to JSON.


## Tablet controls

See `TABLET_ENGINE_2.md`.

- [Form Engine](FORM_ENGINE.md)
- [Print and Export Center](UNIVERSAL_PRINT_CENTER.md)

## Specialized Gas Ratio & Pixler forms

The form manager includes factory templates for depth interpretation, time monitoring,
normalized-gas QC, and detailed C1–C5 review. Column and parameter captions are created in
English; a factory template is edited through an independent user copy.

Basic LAS forms are populated automatically from the current file and can be saved as editable user templates.

## LAS text recovery

Import now detects UTF-8, Windows-1251, and DOS CP866 automatically. Mojibake such as
`‘Є®а®бвм` is repaired before curve lists, tablet headers, and form editors are rendered. The
original LAS bytes remain unchanged.

## Print and Export Center

Use “File → Print and export center...” (`Ctrl+P`) for the active chart or tablet. In Form Manager, use “Print / export” for the selected form. The center supports the native Windows/Linux printer, PDF, PNG, JPEG/JPG, TIFF, BMP, WebP, and SVG.

Choose A4, A3, custom or roll media, portrait/landscape orientation, four page margins, 72–600 DPI, and JPEG/WebP quality. Raster files are generated at the full paper pixel dimensions for the selected DPI. “Auto-fit columns” includes every visible column, including tracks outside the horizontal viewport, without clipping. Preview and final output share one renderer and do not alter working tablet widths.

## Human-readable LAS table headers

The LAS table now defaults to a friendly parameter name plus the original mnemonic and canonical
mapping, for example `Methane content / S800 → C1 / [%]`. A header mode selector can show friendly
names only or original LAS mnemonics only. Hovering over a header shows the complete recognition
audit.

## Quick lithology interval creation

In a Lithology column, hold `Shift` and left-drag from the interval top to its bottom. Releasing the
mouse opens a compact dialog where both depths can be corrected and exactly one rock type is
selected. `OK` renders the interval immediately. Cuttings composition, LBA, calcimetry, and rich
text descriptions remain separate sample-editor fields. Save the project with the diskette toolbar
action or `Ctrl+S`.

## Editable captions and stratigraphy

Every track is fully editable from its right-click menu: title, section, width, X axis, parameters,
captions, styles, scales, and ranges. Stratigraphy now has a project catalog, `Shift + left drag`,
a dedicated toolbar mode, double-click editing, and project persistence. See [Editable form captions
and stratigraphy](FORM_CAPTIONS_AND_STRATIGRAPHY.md).

## LAS Editor 2

Added an ascending copy for descending LAS, progressive merging, external-curve insertion,
pencil edits with synchronous recalculation, an Excel-like table, and XLSX/TSV/CSV exports.
See [LAS Editor 2](LAS_EDITOR_2.md).

- The graphical pencil can now be started from the toolbar or track context menu, explicitly selects a source curve and shows a preview stroke.

## Form and print Constructor

Open **Constructor** or press `Ctrl+Shift+K`. Guide: [CONSTRUCTOR.md](CONSTRUCTOR.md).

## Constructor 0.7.1: text and lithotypes

Stratigraphy, form structure, and WYSIWYG header editors can use horizontal text, 90°
bottom-to-top, or 90° top-to-bottom, positioned near the upper edge, centred, or near the lower
edge. For stratigraphy these positions correspond to top, interval centre, and base.

All 117 standard rock patterns are immediately available in lithology and cuttings with real
thumbnails. Headers can contain a dynamic legend or an individual lithotype swatch. The catalog
supports project rocks, factory overrides, and reset. See the [Constructor guide](CONSTRUCTOR.md).

## Exact lithotype patterns 0.7.2

The standard rocks use the original BMP files from both supplied catalogs. Patterns are tiled
without smoothing and do not stretch while depth is zoomed. Labels over lithology and cuttings
are hidden by default and can be enabled in the track or form-structure editor. The same images
are used by header legends, preview, PDF and print.

## Planned unified interval report

After the print Constructor is stabilized, the current calcimetry/LBA PDF will be extended into a
combined report containing top/bottom/thickness, stratigraphy, lithology, cuttings composition,
only manually entered rock descriptions, LBA, calcimetry, C1–C5, total gas, Gas Ratio/Pixler,
H₂S/CO₂, drilling channels and depth events. Planned formats are PDF, DOCX, XLSX, CSV/TSV and
HTML. See the [report export plan](REPORT_EXPORT.md).
