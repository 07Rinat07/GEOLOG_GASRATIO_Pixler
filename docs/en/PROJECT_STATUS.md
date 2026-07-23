# Project status

Snapshot: 23 July 2026. Version: 0.7.43, test build.

## Completed

- the welcome window remains visible for at least 3000 ms without blocking `sleep`, then fades out over 180 ms;
- project format v18 with a safe v17 → v18 migration;
- persisted acquisition schema v1 in `well.acquisition_sessions`;
- immutable index/curve schema and append-only `DATA_ROW`, `EVENT_UPSERT`, and `EVENT_DELETE`;
- contiguous sequence, bounded buffering, and explicit backpressure without record loss;
- atomic dataset/event/journal rollback on apply failure;
- checkpoints with row count and dataset/events/audit SHA-256 fingerprints;
- deterministic replay from zero or after a verified checkpoint;
- identical rows, operational events, QC flags, and report projection after replay;
- closed sessions with a final checkpoint and final audit digest.

Focused startup/version set: 13 passed. Available headless regression: 964 passed,
4 skipped, and 3 deselected because `lasio` is unavailable. The full Qt/LAS/Ruff/mypy gate and
Windows/HiDPI/PDF/physical-print smoke tests remain mandatory.

Next slice: versioned lag/depth correction without modifying the append-only source.

See [Acquisition replay](ACQUISITION_REPLAY.md) and the [engineering status](../PROJECT_STATUS.md).
