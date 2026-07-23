# Release notes 0.7.37 — shared coverage model

- added one headless coverage analyzer;
- zero, a missing sample, and an unavailable channel are no longer conflated;
- `ReportDefinition` and Report Passport now use schema v2;
- CSV writes `0`, an empty cell, and `#N/A`; XLSX also exposes coverage statistics;
- JSON/Parquet and the passport include structured coverage payloads;
- v1 definition payloads migrate at runtime and project format remains v16.

See [Coverage model](COVERAGE_MODEL.md).

Проверки / checks: 57 focused passed, 1 optional skipped; 876 passed, 4 skipped, 3 LAS tests deselected.
