# WITS Level 0 capture and parsing

## Purpose

**File → Capture WITS Level 0...** receives a GSWITS TCP stream, preserves the incoming bytes
unchanged, and passes every complete frame through a typed parser. In version 0.7.76, a confirmed
Import Review can start an append-only `AcquisitionSession`; the raw boundary and parser remain
immutable, while Dataset mutation occurs only through `AcquisitionController`.

## TCP server setup

Use this mode when GSWITS is configured as an **outgoing connection (TCP client)**.

1. Select **Incoming connection — TCP server**.
2. Use `0.0.0.0` for all local interfaces or a specific local IP.
3. Enter the same port to which GSWITS connects.
4. Select the raw-data directory and press **Start capture**.
5. Save the GSWITS settings and verify the connection state.

## TCP client setup

Use this mode when GSWITS is configured as an **incoming connection (TCP server)**.

1. Select **Outgoing connection — TCP client**.
2. Enter the GSWITS computer IP and port.
3. Press **Start capture**.
4. After a disconnect, Pixler retries with bounded increasing delay.

## Preserved data

Every connection gets a separate directory. `*.wits` files contain the exact incoming bytes, while
`*.chunks.jsonl` records UTC arrival time, offset, TCP chunk size, and connection ID. Segments are
append-only and suitable for deterministic replay.

## Parser pipeline

One `Wits0StreamProcessor` is used by live TCP and replay:

```text
TCP chunk / raw chunk
        ↓
Wits0FrameDecoder: && ... !!
        ↓
Wits0Parser: record/item/raw value
        ↓
profile-driven typing
        ↓
Wits0SequenceTracker
        ↓
immutable Wits0ParsedFrame + diagnostics
```

The parser supports `float`, `integer`, `text`, `date`, and `time`. Standard header items 01–07
cover the record identifier, sequence number, well, wellbore, date, time, and activity code. Items
08–99 are resolved through `geoscape-gswits.json`.

A malformed line does not reject the whole frame. Its original line, raw value, unknown
`record/item`, and conversion error remain in the deterministic discovery snapshot used by Import Review.

## Sequence-number control

Sequence numbers are tracked independently for each record number. States are:

- `first` — the first sequence for that record;
- `contiguous` — the expected next value;
- `duplicate` — a repeated last sequence;
- `gap` — one or more values are missing;
- `out_of_order` — an older value arrived;
- `invalid` or `unavailable` — item 02 is malformed or absent.

A reconnect creates a new stream processor, so sequence state is not carried across different TCP
connections. A raw file can be processed again by the same pipeline.

## Monitor window

- **Latest frames** shows original `&& ... !!` frames.
- **Parsed fields** shows record, sequence status, mnemonic, typed value, unit, and diagnostics.
- **Connections and errors** shows connections, disconnects, raw segments, parser warnings, and
  errors.
- The status panel counts fields, parser warnings/errors, and sequence anomalies.

Closing the window stops the worker and closes files.

## Import Review

After frames have been received, press **Import Review…**. The dialog operates on an immutable
snapshot and:

1. shows every detected `record/item`, source mnemonic, type, UOM, statistics, and samples;
2. proposes semantic bindings through the Semantic Channel Dictionary;
3. selects WITS header datetime or a numeric depth/time field as the active index;
4. supports hide, canonical mnemonic/kind, quantity class, and UOM overrides;
5. blocks non-numeric curves, incompatible quantity classes, and required numerical UOM conversion;
6. atomically creates an immutable `AcquisitionDatasetSchema`;
7. saves the mapping as a separate versioned JSON profile without modifying the built-in GeoScape profile.

The fingerprint describes the mapping surface, so more values for existing fields do not invalidate
a confirmation. A new `record/item`, changed inferred type/UOM, or newly available index source
marks the schema **Stale** and requires another review. **Reset discovery** clears only the current
snapshot and commit; saved versioned profiles remain on disk.

## AcquisitionSession

After confirming the schema, select the current well and press **Start session**. The application:

1. converts received frames into immutable normalized measurement batches;
2. places records into a bounded queue atomically, without partial enqueue;
3. applies the configured `DRAIN_THEN_RETRY` policy under backpressure;
4. writes rows only through `AcquisitionController`;
5. creates checkpoints only when the pending queue is empty;
6. shows pending, applied, skipped, checkpoints, and backpressure;
7. on **Close session**, stops intake, drains the queue, and creates the final checkpoint.

The growing Dataset is selected immediately in the project tree. **Flush queue** manually applies
all pending records. Closing the window during an active session first stops the TCP worker,
processes remaining immutable events, and performs controlled close. Full contract:
[WITS0_ACQUISITION.md](WITS0_ACQUISITION.md).

## Limitations

- the GeoScape profile is based on the GSWITS manual and must be confirmed against a real stream;
- unknown fields are preserved and editable in Import Review but require manual confirmation;
- numerical UOM conversion is not yet performed: source and canonical UOM must resolve to the same canonical unit;
- current values and dedicated live time/depth graphs are the next increment;
- reconnect does not yet create separate connection-gap records, and a new session for a previously used well requires an explicit policy;
- do not expose the WITS0 port directly to the internet;
- raw files do not replace project saving with **Ctrl+S**.
