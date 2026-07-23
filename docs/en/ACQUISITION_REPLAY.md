# Append-only acquisition and deterministic replay

Status: implemented in 0.7.42. Acquisition schema: v1. Current project format: v19 (acquisition introduced in v18).

A recorded `AcquisitionSession` is the primary source. The growing `Dataset` and
`operational_events` collection are verified projections that must replay to identical rows,
events, QC flags, and report data.

## Contract

- one session pins an immutable index and curve schema;
- records use a contiguous sequence and `DATA_ROW`, `EVENT_UPSERT`, or `EVENT_DELETE` kind;
- rows are append-only and a missing curve sample becomes `NaN`;
- a bounded buffer reports explicit backpressure and never drops a record;
- an apply failure atomically restores the dataset, events, and source journal;
- a checkpoint signs row count, dataset/events fingerprints, and a combined audit digest;
- replay runs on a working copy, starts from zero or resumes only after a matching checkpoint, validates metadata/fingerprints, and commits only as a whole;
- a closed session requires a final checkpoint and matching final audit digest.

Project format v18 introduced sessions; current v19 stores them in `well.acquisition_sessions`. Migration `v17 → v18` adds an
empty collection without changing existing project data. Versioned lag/depth correction is
implemented in 0.7.44 as a separate derived projection that leaves the append-only source unchanged.
