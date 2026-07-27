# GEOLOG GASRATIO@Pixler 0.7.78 — WITS0 reliability and restart recovery

## Connection lifecycle

WITS0 TCP connection and disconnection boundaries now have stable connection IDs, an append-only
fsync-backed JSONL journal, and typed acquisition records. Open sessions store connection state,
peer, close reason, raw segment, bytes and frames through `AcquisitionController` without creating
artificial measurement rows.

## Disk guard and raw retention

The capture worker checks free disk space before raw writes and during idle socket intervals. A
warning threshold is visible in the monitor; crossing the critical threshold stops capture
explicitly before data can be accepted without raw persistence. Configurable retention removes only
inactive raw segments and sidecars, protects the active file, and honours age, byte and minimum-file
limits.

## Restart recovery

An atomic recovery manifest records the current run, connection, raw segment, acquisition session
and custom profile. Startup detects an unclean previous run and repairs crash-truncated chunk-index
JSONL tails without modifying `.wits` bytes. A persisted open WITS0 `AcquisitionSession` can be
reconstructed from its immutable schema and versioned custom profile, preserving acquisition
sequence and checkpoints.

## Workspace persistence

Live monitor axis mode, auto-follow, pause-view, follow span, rendering budget, selected curves,
history range and active session ID are persisted per well through `QSettings`.

## Windows soak tooling

Added `tools/wits0_soak_test.py` and `scripts/run_wits0_soak_test.ps1`. The loopback test exercises
random TCP chunking, reconnects, gaps, duplicates, malformed values, raw rotation, retention,
connection journaling and clean recovery-manifest closure, then writes a machine-readable JSON
report.

## Compatibility and boundary

Project format remains v20, form schema v8 and tablet layout v18. The release does not claim a
passed real GSWITS soak, physical disk-full exercise, Windows Service installation or signed field
acceptance. Those remain field-gate activities.
