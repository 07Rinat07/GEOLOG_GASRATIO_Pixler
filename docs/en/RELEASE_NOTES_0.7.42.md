# Release notes 0.7.42 — append-only acquisition and replay

- added a persisted acquisition session with an immutable dataset schema;
- rows and operational events are recorded in a contiguous append-only journal;
- implemented bounded buffering, backpressure, atomic rollback, and controlled close;
- checkpoints sign row count, dataset/events projections, and a combined audit digest;
- replay from zero or a verified checkpoint transactionally reproduces rows, events, QC, and reports and validates metadata;
- upgraded project format to v18 with a safe v17 → v18 migration;
- the next slice is versioned lag/depth correction without changing the source journal.

Verification: 127 focused tests passed; headless: 952 passed, 4 skipped, 3 deselected.
