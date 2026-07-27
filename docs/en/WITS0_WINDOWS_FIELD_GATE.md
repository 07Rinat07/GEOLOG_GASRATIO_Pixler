# WITS0 Windows field reliability gate

## Status

This gate runs in parallel with WITSML development on the target Windows workstation connected to
real GeoScape/GSWITS traffic. Release 0.7.79 supplies the software and checklist but does not claim
that the physical field gate has passed.

## Required setup

Record the workstation, Windows build, application build and SHA-256, GSWITS connection mode,
actual IP/port, enabled records and intervals, raw-storage volume, free-space thresholds, retention
policy, NTP source and test operator. Ports shown in vendor screenshots are examples and must not be
assumed.

## Minimum run

Run at least 8 hours; 24 hours is preferred. Include normal traffic, one controlled GSWITS restart,
one application restart with an open acquisition session, network interruption and recovery, raw
rotation, project save/reopen, live-monitor pause/resume and history navigation.

## Acceptance evidence

Collect the raw `.wits` segments, chunk indexes, connection journal, recovery manifest, project
file, application log, soak JSON report and screenshots of connection/live-monitor state. Verify:

- no accepted TCP bytes exist without a raw reference;
- connection IDs and disconnect reasons are complete;
- replay produces the same parsed/discovery result as live capture;
- acquisition sequence and checkpoints continue after restart;
- disk warning/critical thresholds behave as configured;
- active raw files are never removed by retention;
- no unhandled exception, UI freeze or growing memory trend is observed;
- final recovery manifest reports a clean shutdown.

A failed criterion keeps the gate open. The report must identify the failing timestamp, connection
ID, raw segment and corrective build.
