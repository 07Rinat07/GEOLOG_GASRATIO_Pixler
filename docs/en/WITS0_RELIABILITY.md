# WITS0 reliability, recovery and soak testing

## Scope

The 0.7.78 layer protects the WITS0 raw stream and open append-only `AcquisitionSession` from normal
network disconnects, low disk space, process interruption and lost live-view settings. Raw bytes
remain authoritative: parser, mapping or Dataset failures must not destroy accepted source data.

## Connection records

Each TCP connection receives a stable `connection_id`. The worker writes an append-only JSONL run and
connection journal. While an `AcquisitionSession` is open, connection boundaries are also appended
through `AcquisitionController` as typed `OperationalEventKind.CONNECTION` records. Peer, reason,
raw segment, bytes and frame count are preserved without creating fake Dataset rows.

## Disk guard and retention

`Wits0DiskSpaceGuard` checks free space before raw writes and while the socket is idle. Warning state
continues capture; critical state rejects the next raw write, closes the connection with
`critical_free_space`, and fails explicitly. `Wits0RawRetentionManager` deletes only inactive `.wits`
segments and known sidecars, protects the active segment, and applies age/size/minimum-count limits.
It never deletes journals, manifests or projects.

## Restart recovery

An atomically replaced `.wits0-recovery.json` stores run, connection, current segment, last receive
time, acquisition session and custom profile context. Startup detects an unclean previous run.
Truncated chunk-index JSONL tails are repaired atomically and unindexed raw tails are reported;
`.wits` bytes are never rewritten.

An open persisted WITS0 session is resumed from its immutable schema and versioned custom profile,
keeping sequence and checkpoints continuous. Closed sessions are not reopened.

## Workspace persistence

Per-well `QSettings` store axis mode, auto-follow, pause-view, follow span, rendering budget,
selected curves, history range and active session ID. This is presentation state only.

## Windows soak test

```powershell
.\scripts\run_wits0_soak_test.ps1 -DurationHours 8 -RateHz 20
```

The headless Python generator uses random TCP chunk boundaries, reconnects, sequence gaps,
duplicates and malformed values, then writes a JSON report. Synthetic loopback testing does not
replace a real GeoScape GSWITS field soak.

## Boundaries

No Windows Service is installed, active raw data is never removed, closed sessions are not reopened,
and no real field soak is claimed. Service/startup evaluation, a signed checklist, physical
disk-full testing and long-duration GSWITS validation remain acceptance work.
