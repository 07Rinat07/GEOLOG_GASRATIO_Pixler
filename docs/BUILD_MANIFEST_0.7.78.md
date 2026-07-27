# Build manifest — GEOLOG GASRATIO@Pixler 0.7.78

## Release identity

- Package version: `0.7.78`
- Project format: `v20`
- Form schema: `v8`
- Tablet layout: `v18`
- Main increment: WITS0 connection records, disk guard, raw retention, restart recovery, workspace persistence and Windows soak tooling.
- Compatibility: no project/form/tablet schema migration.

## Implemented reliability boundary

- Atomic recovery manifest and append-only fsync JSONL connection journal.
- Typed connection/disconnection acquisition records through the bounded `AcquisitionController` queue.
- Configurable warning and hard-critical free-space thresholds.
- Retention of inactive raw segments only, with active-path protection and age/size/minimum-count limits.
- Crash-truncated JSONL sidecar repair without modifying source `.wits` bytes.
- Reconstruction of persisted open WITS0 sessions from immutable Dataset schema plus versioned custom profile.
- Per-well live-monitor workspace state through `QSettings`.
- Windows-oriented loopback soak tooling: `tools/wits0_soak_test.py` and `scripts/run_wits0_soak_test.ps1`.

## Validation performed in the release container

- Targeted headless release gate: **183 passed, 4 skipped**.
- WITS0-focused gate: **47 passed, 3 skipped**.
- Documentation audit: **104 localized Markdown files per language**, **2104 synchronized RU/KK/EN keys**.
- Python bytecode compilation: `src`, `tests`, `tools`, `scripts` completed successfully.
- Synthetic loopback soak smoke: **59 frames**, **3 connect/disconnect cycles**, zero parser errors, healthy disk state and clean recovery-manifest closure.
- Full test collection visibility: **1276 tests collected, 83 collection errors** because `PySide6`/`pyqtgraph` are unavailable in this Linux container. A full Windows Qt run is therefore not claimed.
- Ruff was not run because the executable is not installed in the container.

## Wheel

- File: `geolog_gasratio_pixler-0.7.78-py3-none-any.whl`
- Size: `2997909` bytes
- SHA-256: `3dc1b61c29a4c2c7abe99c3b9726ad9eb6ea4c5ea301bec9ffd535eae5577129`
- ZIP integrity: passed.
- Isolated no-dependency installation: passed.
- Headless smoke imports: package version, reliability contracts and built-in GeoScape WITS0 profile passed.

## Remaining field gates

- Real 8–24 hour Windows soak against anonymized GSWITS traffic.
- Controlled low-space/physical disk-full exercise on the target workstation.
- Windows startup/service strategy evaluation.
- Signed field smoke checklist.

The source-archive hash is intentionally reported in the external release handoff because embedding the archive hash inside the archived manifest would be recursive.
