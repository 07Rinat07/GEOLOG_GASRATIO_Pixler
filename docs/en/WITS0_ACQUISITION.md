# WITS0 AcquisitionSession

## Purpose

This document describes the stage after **Import Review** confirmation. Before a session starts, the application must have an immutable `Wits0ImportReviewCommit` containing the reviewed `AcquisitionDatasetSchema`, selected index, and versioned custom profile.

## Pipeline

```text
Wits0ParsedFrame
    ↓ Wits0FrameNormalizer
Wits0MeasurementBatch
    ↓ bounded queue
AcquisitionRecord(DATA_ROW)
    ↓ AcquisitionController
append-only Dataset + AcquisitionSession
```

The raw `*.wits` file is not modified. The normalizer retains the source frame SHA-256, `record/item`, source sequence, reception timestamp, and raw reference.

## Index

For `header:datetime`, items 05 and 06 are combined with the explicitly confirmed timezone, converted to UTC, and stored as Unix nanoseconds. A depth/time field index uses only the selected field. A frame without a valid index does not create a row.

## Channel values

Every row contains the exact curve ID set from the immutable schema. A present valid number is stored as `float`; a missing or damaged value becomes `None` and then `NaN` in the Dataset. The selected index field is not duplicated as a curve.

## Sequence policy

The parser tracks source sequence independently for each WITS record. Duplicate, invalid, and out-of-order frames are skipped by default; gaps are accepted and remain diagnostic. Acquisition sequence is not the source sequence: it always starts at 1 and remains contiguous inside the `AcquisitionSession`.

## Bounded queue and backpressure

`AcquisitionController.enqueue_many()` validates capacity, sequence, record IDs, and schema for the entire batch before mutation. On any failure, the pending queue remains unchanged. `RAISE` returns backpressure to the caller; `DRAIN_THEN_RETRY` applies part of the pending records and retries enqueue once.

## Checkpoints

A checkpoint is created only when the pending queue is empty. The runtime supports thresholds by applied-record count and elapsed time. A checkpoint records sequence, row count, Dataset digest, events digest, and audit digest.

## Controlled close

Controlled close:

1. rejects new frames;
2. drains the pending queue completely;
3. creates the final checkpoint;
4. sets `closed_at`;
5. stores the final audit digest;
6. changes the session to `closed`.

After close, new records are rejected. A saved project can be reopened and its append-only projection is verified.

## Operator interface

The WITS0 window provides **Start session**, **Flush queue**, and **Close session**. Status shows pending records, applied rows, skipped frames, checkpoints, and backpressure. Closing the window with an active session performs controlled close after the TCP worker stops and remaining immutable events are processed.

## Open field acceptance

The built-in GeoScape mapping must still be confirmed with a real anonymized GSWITS raw stream. Windows tests must cover reconnect, long-running capture, disk-full behavior, abnormal termination, project reopen, and matching live/replay Dataset digests.
