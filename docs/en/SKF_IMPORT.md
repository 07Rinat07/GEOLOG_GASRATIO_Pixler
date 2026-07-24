# Delphi SKF form import

Version 0.7.14 adds a safe importer for legacy `.skf` files containing a binary Delphi component
stream.

## Output

One SKF file is converted into:

- an editable tablet `FormDocument`;
- a linked print header `MasterlogTemplate`;
- embedded BMP, PNG, or JPEG images when present;
- an import report with source name, size, SHA-256, root class, component count, and warnings.

The form is stored in the user `forms/depth` or `forms/time` library. The linked header appears
among the Constructor's user print forms.

## Import through Form Library

1. Open **Forms → Form Library**.
2. Expand **Import and export**.
3. Click **Import SKF**.
4. Select the `.skf` file.
5. Review the import report and warnings.
6. Open the created user form.

## Import through Constructor

1. Open **Constructor → Tablet forms**.
2. Click **Import SKF form**.
3. Review the report.
4. Open the form in Form Library and the linked header in the print-form section.

## Mapping

When present in the SKF stream, the importer transfers:

- column and header-element geometry;
- captions, sections, alignment, and text direction;
- mnemonics, units, colors, curve width, and line style;
- linear/logarithmic scale and min/max;
- grid settings;
- header fields, text, lines, and images;
- vertical-axis kind: depth or time.

Unknown custom Delphi components are never executed. They are mapped to the nearest internal type
or skipped with a warning.

## Safety

No Delphi class is instantiated and no event handler is executed. The stream is parsed into a
neutral tree with limits on file size, binary-property size, nesting depth, and component count.
The source SKF is opened read-only.

## Saving and result verification

Import adds the form and resources to the current project/user library. After review, press
**Ctrl+S** and save the form through the library command when a separate reusable form is required.
Closing without saving may discard current project changes. Reopen the form and verify columns,
header, scales, images, text direction, and curve bindings. Run preflight and preview before print.

## Diagnostic tool without GUI

```powershell
python tools\inspect_skf.py "C:\path\form.skf" --dump-json skf-tree.json
python tools\inspect_skf.py "C:\path\form.skf" --convert-dir converted
```

## Limits

Synthetic Delphi streams are covered by tests. Exact verification of vendor-specific controls
requires real SKF files from the source application and visual comparison of form, header, and
printed output.
