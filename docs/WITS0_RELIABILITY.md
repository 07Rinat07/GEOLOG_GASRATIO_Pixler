# WITS0 reliability, recovery and field soak testing

## Scope

The 0.7.78 reliability layer protects the WITS0 raw stream and the open append-only
`AcquisitionSession` against normal network disconnects, low disk space, process interruption and
UI workspace loss. The raw byte stream remains the recovery authority: semantic parsing or Dataset
commit failures must not destroy source data.

## Connection lifecycle records

Every TCP connection receives a stable `connection_id`. The capture worker writes append-only JSONL
records for run start/stop, connection and disconnection under the source raw directory. When an
`AcquisitionSession` is open, connection and disconnection boundaries are also appended through
`AcquisitionController` as typed `OperationalEventKind.CONNECTION` records. They preserve peer,
reason, raw segment, received byte count and parsed frame count without adding fake Dataset rows.

## Disk-space guard

`Wits0DiskSpaceGuard` performs rate-limited free-space checks before raw writes and while an idle
socket is connected. Two thresholds are configurable:

- warning: capture continues and emits a state transition event;
- critical: the next raw write is rejected, the connection is closed with
  `critical_free_space`, and the worker enters `failed` rather than silently losing bytes.

Thresholds are stored in the WITS0 workspace settings and can be changed only while capture is
stopped.

## Raw retention

`Wits0RawRetentionManager` deletes only inactive `.wits` segments and their known
`.chunks.jsonl`/`.meta.json` sidecars. The active segment is protected. Retention can be limited by
age and total raw bytes while retaining a configurable minimum number of complete segments.
Connection journals, recovery manifests and project files are never retention candidates.

## Restart recovery

The source directory contains an atomically replaced `.wits0-recovery.json` manifest with run,
connection, current raw segment, last reception timestamp, acquisition session and custom profile
context. A new run detects an unclean previous state.

Before opening sockets, `recover_wits0_raw_directory()` validates chunk-index JSONL files, removes a
crash-truncated invalid tail atomically and reports raw bytes that are not covered by a valid index.
It never rewrites `.wits` bytes.

When a project contains an open WITS0 `AcquisitionSession`, the capture dialog reconstructs the
normalizer contract from the persisted immutable `AcquisitionDatasetSchema` and versioned custom
profile. The same session resumes with continuous acquisition sequence and existing checkpoints.
Closed sessions are not reopened.

## Workspace persistence

The live monitor stores per-well state through `QSettings`:

- axis mode;
- auto-follow and pause-view;
- follow span;
- rendering budget;
- selected curves;
- history range;
- active acquisition session identifier.

Workspace state is presentation-only and does not modify the Dataset or append-only record history.

## Windows soak-test tooling

Run a default eight-hour loopback test from PowerShell:

```powershell
.\scripts\run_wits0_soak_test.ps1 -DurationHours 8 -RateHz 20
```

The headless `tools/wits0_soak_test.py` generator sends deterministic WITS0 records through random
TCP chunk boundaries, reconnects periodically and can inject sequence gaps, duplicates and malformed
values. It writes a JSON report containing producer/capture counters, disk and retention state,
recovery manifest and raw inventory. A successful synthetic soak does not replace a real GeoScape
GSWITS field test.

## Deliberate boundaries

This slice does not install a Windows Service, delete active raw data, auto-open a closed session, or
claim a passed real rig soak test. A service/startup strategy, signed field checklist, real disk-full
exercise and long-duration GSWITS validation remain release-acceptance work.
