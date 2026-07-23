# Shared ReportDefinition

`ReportDefinition` is the immutable description of one report. It freezes the dataset, exact
index, sections, curves, form, language, and interval mode before preview or export starts.

## Interval modes

- `full` — the full selected axis;
- `current` — the viewport frozen when Print Center opens;
- `custom` — explicit user boundaries;
- `selection` — the synchronized selection only when it belongs to the same axis.

The resolver validates the dataset/index, clamps the range to real data, creates one inclusive
row set, and returns `ResolvedReportDefinition`. Preview, PDF/printing, and CSV/XLSX do not
recalculate the interval independently.

## Integrated paths

- Print Center: one resolved range for preview and the final job;
- Masterlog: one depth range for preview, PDF, and system preview;
- selected-interval export: identical curve IDs and rows for CSV/XLSX;
- Report Passport: the canonical definition payload and SHA-256 are stored in the sidecar.

Tablet reports preserve the selected `vertical_index_id`; a DEPTH selection cannot be applied
to a TIME view. Project format remains v16.

Full engineering contract: [REPORT_DEFINITION.md](../REPORT_DEFINITION.md).
