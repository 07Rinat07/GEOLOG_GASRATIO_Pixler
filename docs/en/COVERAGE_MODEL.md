# Shared coverage model

Version 0.7.37 distinguishes four data states:

- `observed_value` — a finite non-zero value;
- `observed_zero` — a real finite zero;
- `missing_sample` — the channel exists but the sample is `NaN/Infinity`;
- `channel_unavailable` — the report requested a channel absent from the dataset.

`ReportDefinition` schema v2 accepts stable curve IDs and expected mnemonics. The resolver keeps
unresolved mnemonics as unavailable channels and calculates coverage only for rows in the
resolved interval.

CSV writes zero as `0`, a missing sample as an empty cell, and an unavailable channel as `#N/A`.
XLSX adds availability, observed, zero, missing, and coverage columns on the `Parameters` sheet.
JSON, Parquet, and Report Passport schema v4 include the structured coverage payload.

Project format remains v16. Full contract: [COVERAGE_MODEL.md](../COVERAGE_MODEL.md).
