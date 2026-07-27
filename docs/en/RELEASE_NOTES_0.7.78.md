# GEOLOG GASRATIO@Pixler 0.7.78 — WITS0 reliability and recovery

Added stable connection IDs, an append-only JSONL lifecycle journal and typed connection records in
open acquisition sessions. Added a pre-write disk-space guard and configurable retention that only
removes inactive raw segments. Added an atomic recovery manifest and safe repair of truncated chunk
index tails without changing `.wits` bytes.

Open persisted WITS0 sessions can resume from immutable schema plus versioned custom profile with
continuous sequence and checkpoints. Live axis/follow/pause/history/curve selections are persisted
per well. Added headless Python and PowerShell Windows soak-test tooling for reconnect, chunking,
gaps, duplicates and malformed values.

Project format remains v20. A real GSWITS soak, physical disk-full test, Windows Service and signed
field checklist are not claimed by this release.
