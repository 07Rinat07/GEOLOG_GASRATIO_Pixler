# Project status

Snapshot: 23 July 2026. Version: 0.7.42, test build.

## Completed

- project format v18 with a safe v17 → v18 migration;
- persisted acquisition schema v1 in `well.acquisition_sessions`;
- immutable index/curve schema and append-only `DATA_ROW`, `EVENT_UPSERT`, and `EVENT_DELETE`;
- contiguous sequence, bounded buffering, and explicit backpressure without record loss;
- atomic dataset/event/journal rollback on apply failure;
- checkpoints with row count and dataset/events/audit SHA-256 fingerprints;
- deterministic replay from zero or after a verified checkpoint;
- identical rows, operational events, QC flags, and report projection after replay;
- closed sessions with a final checkpoint and final audit digest.

Expanded focused set: 127 passed. Available headless regression: 952 passed,
4 skipped, and 3 deselected because `lasio` is unavailable. The full Qt/LAS/Ruff/mypy gate and
Windows/HiDPI/PDF/physical-print smoke tests remain mandatory.

Next slice: versioned lag/depth correction without modifying the append-only source.

See [Acquisition replay](ACQUISITION_REPLAY.md) and the [engineering status](../PROJECT_STATUS.md).
