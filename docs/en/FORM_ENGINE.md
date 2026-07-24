# Form Engine

Form Engine stores editable depth and time forms independently from a concrete LAS file.
A form references canonical parameters, while the mnemonic dictionary resolves them to curves in
the active dataset.

## Implemented first slice

- versioned form schema v1;
- form, column, track and parameter-binding models;
- depth and time form types;
- identifier, width, range and duplicate-link validation;
- UTF-8 JSON, atomic persistence and schema-v0 migration;
- user-form repository;
- read-only factory templates and editable copies;
- basic depth, basic time, gas components, Gas Ratio, Pixler and interpretation templates.

The visual form editor is the next stage and will use these models as the single source of truth.

## Form manager

The manager lists factory and user templates and supports create, copy, rename, delete, JSON import/export, and applying a form to the open dataset. Missing parameters do not abort the build and are reported in diagnostics.

## Visual form structure editor

Users can add, remove, and reorder columns and tracks, edit column widths, titles, and track types, preview the structure, and save the result to a user JSON template. Factory templates remain protected and are edited through a user copy.

## Track content editor

A selected track can be opened in a dedicated parameter editor. It supports:

- adding a canonical parameter from the Sensors catalog;
- adding a concrete curve from the active LAS dataset;
- removing and reordering `ParameterBinding` entries;
- display name, canonical identifier, source mnemonic, and unit;
- visibility, color, line width, and line style;
- linear or logarithmic scale;
- automatic or explicit range.

Changes are stored in the user JSON template and consumed by the existing Form Apply Engine. Source LAS names and values are not modified.


## Live preview
The editor uses a safe draft copy, supports automatic preview, manual apply, saving without closing the editor, and reverting to the last saved version.

## Specialized Gas Ratio & Pixler forms

The following read-only factory forms can be opened directly or saved as editable user copies:

- **Gas Ratio & Pixler — depth interpretation**: depth, drilling, mud, raw and normalized gas,
  C1–C5, Gas Ratio, Pixler, lithology, and interpretation intervals;
- **Gas Ratio & Pixler — time monitoring**: time axis, drilling parameters, gas components,
  ratios, and intervals;
- **Normalized gas QC**: raw and normalized curves, normalization factor, and validity flag;
- **Detailed C1–C5**: separate C1–C3, C4–C5, and isomer-ratio tracks.

Form, column, track, and parameter captions are created in the selected interface language:
Russian, Kazakh, or English. Stable identifiers and canonical parameter links do not change when
the language changes.

## Working LAS base forms

The basic depth and time forms are no longer empty placeholders. Once a dataset is open, they are
populated automatically from the actual curves in the current LAS file. Curves are grouped into
Drilling, Drilling fluid, Gas data, Petrophysics, D-exponent, and Other LAS curves columns, with no
more than four curves in one column so labels remain readable.

Each binding preserves the exact source mnemonic, readable description, unit, Sensors-catalog
color, and recommended range. A form can be opened on the tablet immediately. Edit creates a user
copy where names, contents, order, scales, and styling can be changed and saved for reuse. The form
manager reports available and missing parameters and prevents applying a depth/time form when the
corresponding dataset axis is absent.
## Working LAS form rendering hotfix

Fixed the failure that left the tablet empty after a form was selected. A safe default curve
style is now created correctly, and `PlotDataItem` construction is compatible with
`pyqtgraph 0.14` and `PySide6 6.11`. A GUI regression test now requires the factory depth
form to materialize and actually render the curves of the open LAS dataset.

## Range recovery and resilient form manager

Legacy user forms and Sensors catalogs can contain `0 .. 0` ranges, reversed bounds, or only one
bound. These records no longer block opening or switching forms: reversed finite bounds are ordered,
while incomplete, equal, non-finite, and invalid logarithmic ranges fall back to autoscale. A damaged
user-form JSON file is skipped without deletion and does not make the remaining forms unavailable.

## A4 form print layout

All factory and user forms use one adaptive print renderer. The Form Manager selects
**A4 — portrait** or **A4 — landscape**, while “Auto-fit columns” balances every visible track
across the sheet width. The depth column keeps its own readable minimum, an excessively wide
screen track cannot consume the full sheet, and horizontally scrolled off-screen columns are
printed as well. Print preview and PDF export restore the original screen widths and do not alter
the project layout. Disabling auto-fit preserves the form's original proportions.


## Universal Print and Export Center

All factory and user forms use one page renderer. Form Manager can send the selected compatible form directly to the Print and Export Center. The center supports the native physical printer, PDF, PNG, JPEG/JPG, TIFF, BMP, WebP, and SVG. It provides A4, A3, custom and roll media, portrait/landscape orientation, four independent margins, 72–600 DPI, and JPEG/WebP quality. Raster output is generated at the physical paper pixel dimensions for the selected DPI. Every visible track is printed, including tracks outside the horizontal viewport; temporary print widths are restored after rendering.

## Curated working-form library

Form Manager exposes three protected built-in working templates and all user forms. A separate duplicate MASTERLOG template is not created:

1. **Integrated mud logging form — geology, drilling and gas**;
2. **MASTERLOG — geological and geochemical form**;
3. **Engineering and drilling monitoring — time form**.

The names are polished and localized consistently in Russian, Kazakh, and English. The templates
ship with a clean installation and cannot be overwritten accidentally. Editing creates an
independent user copy that retains section groups, column order, widths, parameter bindings,
scales, and styles. Legacy IDs remain readable for project compatibility.

`FormColumn.group_title` stores the section caption. Form application propagates it to
`TrackDefinition.group_title`, layout persistence keeps it, and the tablet renders one merged
caption above adjacent columns. Column order is defined entirely by the template.

## Shared cuttings sample

Cuttings, LBA, Calcimetry, and Description belong to one `CuttingsSample`. Re-editing updates the
same object atomically by `sample_id`, so linked tracks cannot drift apart or create duplicates.
Validation allows up to four rock components with an exact `100%` total; calcite plus dolomite may
not exceed `100%`.

## Compact geological columns

The default widths of **Stratigraphy**, **Lithology**, **Cuttings log**, **Calcimetry**, **LBA**,
and **Depth** are reduced by **40%** in all factory forms and in saved user forms after the one-time migration. This
releases horizontal space for drilling, gas, and other graph tracks. Curve, gas, interpretation,
and text tracks are not compacted automatically.

Compact kinds can be resized from **48 to 2000 px**. Ordinary graph and text tracks retain the
safe **80 px** minimum. Width can be changed by dragging the right edge with the mouse, through
the track inspector, or in the form structure editor.

Legacy user forms using schema v6 migrate to v7 on first open: only the listed compact columns are
reduced. Saved tablet layouts v16 migrate to v17 in the same way. Once saved, the same form is not
reduced again. User names, ordering, parameter bindings, and all other graph widths are preserved.

Preview, PDF, and physical printing in **Actual size** mode use the saved compact proportions.
**Fit columns** may temporarily redistribute widths for the selected paper without changing the
working form.


## Creating and naming a new form

**Create form** opens a dedicated window that keeps the library visible until the new name is
confirmed. The left side lists **all built-in and user forms**, not only the manager's short curated
set. Search and the **Name**, **Axis**, and **Origin** columns are available.

Selecting an existing form shows its description, vertical-axis type, origin, column, track, and
parameter counts, visible column names with saved widths, and the mnemonics of bound parameters.
This lets the user review established naming patterns before creating an unclear or duplicate name.

The bottom section accepts the new form name and the **Depth** or **Time** axis. The application
removes accidental leading and trailing spaces and collapses repeated internal whitespace. An exact
match with an existing form is blocked regardless of letter case or extra spacing. Once an available
name is entered, **Create** becomes enabled and the form is stored in the user library.
