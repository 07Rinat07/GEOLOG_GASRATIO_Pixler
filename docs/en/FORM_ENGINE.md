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
