# Delphi SKF form import

Version 0.7.14 adds a dedicated safe importer for legacy `.skf` files containing a binary Delphi component stream.

## Output

One SKF file is converted into:

- an editable tablet `FormDocument`;
- a linked `MasterlogTemplate`, the project's internal HeaderTemplate model;
- embedded BMP, PNG or JPEG header images when present;
- an import report containing source name, size, SHA-256, root class, component counts and warnings.

The form is stored under the user `forms/depth` or `forms/time` library. The linked header appears among the Constructor's user print templates.

## Use

In **Forms → Form Library**, expand **Import and export** and choose **Import SKF**. The same command is available in **Constructor → Tablet forms**.

The importer transfers recognized geometry, captions, text orientation, curve mnemonics, units, colours, line styles, scales, min/max ranges, grids, header fields, lines and images. Unknown custom Delphi controls are mapped heuristically or skipped with a warning.

## Safety

No Delphi class is instantiated and no event handler is executed. The stream is decoded into a neutral component tree with limits on file size, binary properties, nesting depth and component count.

## Diagnostic tool

```bash
python tools/inspect_skf.py form.skf --dump-json skf-tree.json
python tools/inspect_skf.py form.skf --convert-dir converted
```

Synthetic Delphi streams are covered. Exact mapping of vendor-specific components still requires the user's real SKF samples for visual comparison.
