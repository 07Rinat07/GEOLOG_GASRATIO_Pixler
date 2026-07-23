# Release notes 0.7.36 — shared ReportDefinition

- added immutable `ReportDefinition` schema v1;
- full/current/custom/selection ranges resolve once against an exact dataset/index;
- Print Center preview and final PDF/print use the same range;
- added the selected-interval range mode;
- Masterlog preview/PDF/system preview and CSV/XLSX use a resolved definition;
- Report Passport stores the definition payload and SHA-256;
- project format remains v16.
- Validation: 50 focused and 865 available regression tests passed; 4 skipped, 3 LAS deselected.


Details: [Shared ReportDefinition](REPORT_DEFINITION.md).
