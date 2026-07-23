# Print media and scale model

Version 0.7.38 uses one model for preview, PDF, paged file export, and the physical printer.

## Media

- A4 and A3;
- custom sheets from 25 to 5000 mm;
- roll media with a user-defined width and content-derived segment length capped at 5000 mm.

## Fit and 100%

**Fit** places the form on one horizontal page. **100%** preserves source column widths at
96 logical pixels per inch and creates continuation pages when the form is wider than the
printable medium. Continuation overlap is configured in millimetres.

The vertical interval is selected independently as current, full, custom, or selection. One
vertical interval may therefore contain several horizontal continuations.

## Physical printer

After the native system dialog, the application validates media support, custom/roll bounds,
minimum margins, printable area, DPI, and the selected page range. Errors block output; nearest-DPI
and multi-page feed warnings are logged.

Use `tools/physical_print_gate.py` to inspect a device. A real test job is sent only with the
explicit `--print-test` flag.

Full engineering contract: [Unified print model](../PRINT_MEDIA_MODEL.md).
