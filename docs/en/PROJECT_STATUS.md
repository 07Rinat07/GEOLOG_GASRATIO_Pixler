# Project status

Snapshot: 23 July 2026. Version: 0.7.41, test build.

## Completed

- six typed operational-event payloads: drilling, gas, show, sample, casing, formation top;
- one envelope with depth/time anchors, canonical UTC timestamps, source, revision, and calibration;
- duplicate, out-of-order, gap, stale, missing-calibration, and expired-calibration QC;
- `OperationalEventController` as the single mutation boundary;
- project format v17 with a safe v16 → v17 migration;
- strict discriminator codec and typed-payload round trip;
- EVENTS/DRILLING reuse exact `ResolvedReportDefinition` bounds;
- removed obsolete import-controller duplicates from the `ui` package.

Expanded focused set: 108 passed. Available headless regression: 936 passed, 4 skipped.
The full Qt/LAS/Ruff/mypy gate and Windows/HiDPI/PDF/physical-print
smoke tests remain mandatory.

Next slice: an append-only growing dataset with checkpoint and deterministic replay.

See [Operational events](OPERATIONAL_EVENTS.md) and the [engineering status](../PROJECT_STATUS.md).
