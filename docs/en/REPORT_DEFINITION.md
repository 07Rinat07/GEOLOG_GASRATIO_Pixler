# Shared ReportDefinition

`ReportDefinition` schema v2 is the immutable description of one report. It freezes the dataset,
exact index, sections, stable curve IDs, expected mnemonics, form, language, and interval mode
before preview or export starts.

The resolver creates one inclusive row set, resolves mnemonics, preserves unresolved requests as
unavailable channels, and calculates coverage. Preview, PDF/printing, and CSV/XLSX do not
recalculate the interval or channel availability.

Schema v1 payloads migrate to runtime schema v2. Project format remains v16.

See the [full contract](../REPORT_DEFINITION.md) and [coverage model](COVERAGE_MODEL.md).
