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
