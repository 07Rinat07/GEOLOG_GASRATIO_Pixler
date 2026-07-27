# GEOLOG GASRATIO@Pixler 0.7.76 — WITS0 normalized batches and append-only AcquisitionSession

## Slice purpose

Version 0.7.76 completes stage D of the WITS0 integration. A confirmed Import Review now converts typed WITS0 frames into immutable normalized measurement batches and writes the growing Dataset only through `AcquisitionController`.

## WITS0 normalization

- `Wits0FrameNormalizer` consumes an immutable `Wits0ImportReviewCommit` and schema digest;
- WITS header date/time is converted to UTC Unix nanoseconds for a `DATETIME` index;
- a depth/time field index is read only from the selected `record/item`;
- missing curve values become `None` and then `NaN` in the Dataset;
- an unknown numeric vendor field can use its confirmed numeric mapping;
- duplicate, invalid, and out-of-order source sequences do not create rows by default;
- raw SHA-256, source record, source sequence, reception timestamp, and raw reference are retained in batch/record provenance;
- live and replay produce identical normalized batches when timestamps and source references are equal.

## Bounded queue and backpressure

`AcquisitionController` now provides atomic `enqueue_many()` and `remaining_capacity`. An incoming batch is either placed into the bounded queue in full or the queue remains unchanged. `Wits0AcquisitionRuntime` supports `RAISE` and `DRAIN_THEN_RETRY`, counts backpressure events, and preserves the contiguous acquisition sequence.

## Checkpoints and controlled close

The runtime creates checkpoints by applied-record count or elapsed time, but only when the pending queue is empty. Controlled close stops intake, drains the queue completely, creates the final checkpoint, and changes `AcquisitionSession` to `closed` with a matching final audit digest. A closed session survives project save/reopen without changing project format v20.

## Interface

After a current Import Review, **File → Capture WITS Level 0...** can:

1. start an acquisition session for the current well;
2. show pending/applied/skipped/backpressure/checkpoint counters;
3. flush the bounded queue manually;
4. perform controlled close;
5. select the growing WITS0 Dataset in the project tree automatically.

The network socket remains in the worker thread, while project mutation occurs in the GUI thread when immutable events are polled.

## Verification

Automated tests cover time/depth indexes, sparse rows, unknown numeric fields, duplicate/out-of-order policy, live/replay equivalence, atomic batch enqueue, backpressure, checkpoint policy, controlled close, and project round-trip. Full GUI runtime still requires a Windows environment with PySide6/pyqtgraph and a real anonymized GSWITS raw stream.

## Compatibility

Project format remains **v20**, form schema **v8**, and tablet layout **v18**. Existing projects require no migration. Compact 50% columns, ready 48/80 widths, all ready and user forms, Ctrl+S save, and reopen behavior remain unchanged.
