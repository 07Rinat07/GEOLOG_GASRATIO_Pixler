# Append-only acquisition and deterministic replay

Status: implemented in 0.7.42. Acquisition schema: v1. Current project format: v20 (acquisition introduced in v18).

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

Project format v18 introduced sessions; current v20 stores them in `well.acquisition_sessions`. Migration `v17 → v18` adds an
empty collection without changing existing project data. Versioned lag/depth correction is
implemented in 0.7.44 as a separate derived projection that leaves the append-only source unchanged.

## Batched materialization

Live mutation is applied in atomic batches of 64 records. Index and curve arrays use geometric
capacity growth and expose only their logical slice; a failed mixed data/event batch restores the
logical row count, curve versions, events and incremental record/dataset/events hash chains without
copying the full projection. `AcquisitionApplyResult` uses `digest_mode=incremental_chain` during
streaming. Full compatible dataset/events fingerprints remain checkpoint and `current_result()`
operations. Replay uses the same batch boundary and ends batches at persisted checkpoints.

## WITS0 raw replay and persistent acquisition boundary

When the bounded LIVE PREVIEW has already evicted early frames, the complete history must not
be reconstructed from the retained RAM tail. Indexed raw capture (`.wits` plus
`.chunks.jsonl`) is used instead. Replay validates contiguous offsets, timestamp ordering, and
connection IDs and fails closed when provenance is corrupt.

Replay is streaming and never materializes the complete raw payload in memory. Each TCP
connection uses the same `Wits0StreamProcessor` as live capture. With an explicitly selected
later boundary, earlier chunks may be consumed only as parser warm-up while the persistent
session receives frames inside the accepted `start_at..end_at` interval. Each stored record
retains the raw SHA-256 and source-segment reference.

## Operator-selected acquisition boundary

When LIVE PREVIEW is truncated, persistent WITS acquisition no longer stops at a generic
warning. The start workflow shows the retained range and indexed-raw status and requires one
explicit choice:

1. **Replay raw and start** — the preferred path. The available interval from the first
   observed preview frame through the current end boundary is processed again through the same
   WITS parser and reviewed runtime.
2. **Start at retained boundary** — the operator deliberately accepts the earliest retained
   frame as the beginning of the persistent Dataset. Earlier preview frames do not enter the
   Dataset, while the original raw remains on disk.

The selected strategy, start/end boundary, and evicted-preview count are persisted as
`AcquisitionRecord.source` provenance tokens. After raw replay, the live handoff suppresses
queued frames already covered by the replay boundary so they cannot be duplicated.
