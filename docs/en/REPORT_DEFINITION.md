# Shared ReportDefinition

`ReportDefinition` schema v2 is the immutable description of one report. It freezes the dataset,
exact index, sections, stable curve IDs, expected mnemonics, form, language, and interval mode
before preview or export starts.

The resolver creates one inclusive row set, resolves mnemonics, preserves unresolved requests as
unavailable channels, and calculates coverage. Preview, PDF/printing, and CSV/XLSX do not
recalculate the interval or channel availability.

Schema v1 payloads migrate to runtime schema v2. Project format v18 stores `well.operational_events` and `well.acquisition_sessions`; events were introduced in v17. For `EVENTS` and `DRILLING`,
`resolve_operational_event_report()` reuses the exact bounds of the existing
`ResolvedReportDefinition`: depth maps to `depth_m`, relative time to `elapsed_time_s`, and
datetime to UTC `measured_at`. The optional `event_kinds` value is a comma-separated kind list.
No second interval resolution is allowed.

See the [full contract](../REPORT_DEFINITION.md) and [coverage model](COVERAGE_MODEL.md).
