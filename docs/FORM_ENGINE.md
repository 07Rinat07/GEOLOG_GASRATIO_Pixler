# Form Engine

Form Engine stores editable depth and time forms independently from a concrete LAS file.
A form references canonical parameters. The mnemonic dictionary resolves those parameters to
curves in the currently opened dataset.

## Implemented first slice

- versioned form schema v1;
- form, column, track and parameter-binding models;
- depth and time form types;
- validation of identifiers, widths, ranges and duplicate links;
- UTF-8 JSON serialization and migration from schema v0;
- atomic repository for user forms;
- read-only factory templates and editable copies;
- factory templates: basic depth, basic time, gas components, Gas Ratio, Pixler and interpretation.

The visual form editor is not part of this slice. It will use these models as the single source
of truth.
