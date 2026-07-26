# GEOLOG GASRATIO@Pixler 0.7.74 — WITS0 raw capture and offline WITSML 2.x inventory

## WITS0 parser and sequence diagnostics

- Added a headless `Wits0Parser` with immutable `Wits0ParsedFrame`/`Wits0ParsedField` results.
- Fields are typed as `float`, `integer`, `text`, `date`, or `time` while retaining the original line and raw value.
- Diagnostics cover unknown records/items, duplicate fields, malformed lines/values, empty values, and NaN/Inf.
- `Wits0SequenceTracker` tracks every record independently and reports first, contiguous, duplicate, gap, and out-of-order states.
- Live TCP and replay share one `Wits0StreamProcessor`; tests prove identical output across different TCP chunk boundaries.
- The capture window now includes parsed fields, parser counters, and sequence anomalies.
- Dataset commit, UOM conversion, and Import Review remain the next increment.


## WITS Level 0

- Added a modeless **File → Capture WITS Level 0...** window that does not block the main
  workspace.
- Both GSWITS connection modes are supported: Pixler as a TCP server and Pixler as a TCP client.
- The TCP client reconnects automatically with a bounded increasing delay.
- Network work is isolated from the Qt GUI; `accept`, `connect`, and `recv` never run in the UI
  thread.
- Original bytes are stored before parsing in append-only `*.wits` segments.
- Every TCP chunk receives a `*.chunks.jsonl` entry with UTC arrival time, offset, size, and
  connection ID.
- The incremental frame decoder handles arbitrary TCP chunk boundaries and extracts complete
  `&& ... !!` frames.
- Live capture and raw-file replay use the same decoder.
- Added a strict GeoScape GSWITS profile schema v1 with 11 records and 105 fields transcribed from
  the GSWITS manual. It remains a starting hypothesis until confirmed by real raw data.

## WITSML 2.x

- Added safe read-only inventory for XML/WITSML files, directories, and ZIP/EPC packages.
- The inventory shows top-level objects, version, UUID, references, and Channel metadata/indexes.
- Archives are never extracted; unsafe paths, DTD/entities, encryption, duplicate paths, and
  resource-limit violations are rejected.

## Limitations

- WITS0 is parsed into `record/item/value`, but UOM mapping and creation of a `Dataset` or
  `AcquisitionSession` are not implemented yet.
- The built-in GSWITS mapping is not proven for a specific installation without a real capture.
- WITSML inventory does not yet read channel arrays or connect through SOAP/ETP.
- WITS0 raw files are separate artifacts and do not replace saving the project with **Ctrl+S**.

Project format remains `v20`, form schema `v8`, and tablet layout `v18`.
