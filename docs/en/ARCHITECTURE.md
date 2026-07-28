
## WITS0 reliability boundary — 0.7.78

`wits0_reliability.py` owns disk policy, retention, sidecar recovery, the atomic run manifest, the
append-only connection journal and workspace codec without importing Qt. Capture checks disk before
raw writes and protects the active segment. Connection boundaries enter an open session only as
typed records through the bounded `AcquisitionController`.

Restart recovery uses the persisted immutable schema and versioned custom profile rather than
invented discovery statistics. `.wits` bytes are never rewritten; only an invalid JSONL sidecar tail
may be atomically removed. `QSettings` stores presentation state only.

SEC-04 makes destructive retention conditional on a valid path-bound application ownership marker. A non-loopback server is valid only with an acknowledged warning and a non-global IPv4 CIDR peer allowlist; accepted sockets outside the allowlist are closed before raw capture and journaled as rejected.
