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

## Factory and ready-form library

The manager keeps two user-visible factory working templates:

1. **Integrated mud logging form — geology, drilling and gas**;
2. **Engineering and drilling monitoring — time form**.

A separate factory MASTERLOG entry is not added to the curated list. Its legacy identifier remains
readable only for project compatibility.

On the first run, the form repository checks the existing application-profile library. Four
confirmed legacy names are atomically promoted to **Ready forms**, polished, and protected from
accidental overwrite:

- `GEO_TECH_GAS_A4_albom` → **Геология, технология и газ — A4, альбомная**;
- `Geo_Tech_Gas_Logging_form A4 albom` → **Геолого-технологический газовый каротаж — A4, альбомная**;
- `Геология_plus_под A4 книжная` → **Геология Plus — A4, книжная**;
- `Форма Мастерлога под A4 книга` → **Мастерлог — A4, книжная**.

A form name is stored once in its JSON, so these exact polished names are shown in RU, KK, and EN interfaces; only the surrounding library labels are localized.

The migration moves the actual columns, tracks, parameters, scales, styles, and widths from the
existing JSON rather than creating empty placeholders. Files are stored under `forms/ready`; old
copies are removed only after a successful atomic write. All other user forms and names remain
untouched. A ready form is opened as a protected template and edited through an independent user
copy. On a new computer without the old profile, these four local forms appear after their JSON
files are transferred or imported.

`FormColumn.group_title` stores a section caption. Applying the form transfers it to
`TrackDefinition.group_title`, persists it in the layout, and renders one shared header above
adjacent columns.

## Shared cuttings sample

Cuttings, LBA, Calcimetry, and Description belong to one `CuttingsSample`. Re-editing updates the
same object atomically by `sample_id`, so linked tracks cannot drift apart or create duplicates.
Validation allows up to four rock components with an exact `100%` total; calcite plus dolomite may
not exceed `100%`.

## Compact geological columns

During upgrade, **Stratigraphy**, **Lithology**, **Cuttings**, **Calcimetry**, **LBA**, and
**Depth** widths are reduced once by **50%**. The conversion covers factory templates, the four
ready local forms, ordinary user forms, and saved tablet layouts. Curve, gas, interpretation, and
text tracks are not reduced automatically.

Compact kinds allow **48–2000 px**. Ordinary graph and text tracks retain an **80 px** safety
minimum. After migration, users can resize a column by dragging its boundary, using Track
Inspector, or using the structure editor; current-schema objects preserve that explicit width
without another automatic reduction.

Forms using schema v7 or older migrate to **form schema v8** on first load. Saved tablets using
layout v17 or older migrate to **tablet layout v18**. Successfully read user forms are immediately
rewritten in the new schema, so the conversion does not depend on a manual resave. Names, order,
parameter bindings, scales, styles, and other graph widths are preserved.

Actual-size preview, PDF, and physical printing use the stored compact proportions. Fit columns may
temporarily redistribute widths for the selected paper, but the working form is restored when the
print operation closes.

## Creating and saving a form with the library visible

Both **Create form** and **Save user form** use one large reference window instead of the old small
name prompt. Until confirmation, the window shows **all ready**, factory, and user forms. It
provides search plus **Name**, **Axis**, **Type**, and **Structure** columns; Structure shows the
column and track counts.

Selecting a form shows its description, vertical axis, type, revision, column/track/parameter
counts, visible columns with stored widths, and bound parameter mnemonics. Search covers names,
descriptions, columns, and parameters.

In **Create form** mode, the user selects a name and the Depth or Time axis. A duplicate is blocked
case-insensitively after whitespace normalization.

In **Save user form** mode, the axis is fixed from the current tablet. An available name creates a
new user form. Matching an existing editable user form displays an explicit replacement warning
and, after confirmation, saves a new revision with the same `form_id`. A ready or factory protected
template name cannot be used. Double-clicking an editable form copies its name into the field for
an intentional update.

The form is written immediately to the local repository. Project data and annotations are separate
and still require **Ctrl+S** to save the project.

