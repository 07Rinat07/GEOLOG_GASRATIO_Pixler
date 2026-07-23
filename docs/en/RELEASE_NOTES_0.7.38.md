# Release notes 0.7.38 — unified print model

- A4/A3/custom/roll use one physical-media model;
- Fit and 100% continuation pages are explicit scale modes;
- preview, PDF, paged files, and the printer share one `PrintDocumentPlan`;
- the page range selected in the system dialog participates in the gate;
- the printer gate validates device state, media, bounds, margins, printable area, and DPI;
- `tools/physical_print_gate.py` prints only with an explicit `--print-test`;
- Report Passport uses schema v3; project format remains v16.

See [Print media and scale model](PRINT_MEDIA_MODEL.md).
