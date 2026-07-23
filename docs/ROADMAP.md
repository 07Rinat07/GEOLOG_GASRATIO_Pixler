# Roadmap — GEOLOG Gas Ratio & Pixler

Updated: 23 July 2026. The roadmap is ordered by risk and dependency. A phase is complete
only when its automated and manual acceptance criteria pass.

## Phase 0 — release recovery

- restore annotation event routing and eliminate the Qt test-process crash;
- resolve all Ruff findings and establish a decreasing, then zero, mypy baseline;
- make the complete pytest suite deterministic on the supported Windows environment;
- run the tablet, annotation, PDF, HiDPI, and physical-printer smoke matrix;
- publish a stable build only after every mandatory gate is green.

Exit: Ruff = 0, mypy = 0, pytest = 0 failures, no process abort, signed smoke checklist.

## Phase 1 — maintainable tablet and reporting core

- split annotation routing, navigation, track lifecycle, grid rendering, and editing out of
  `TabletView`;
- continue splitting state-changing workflows out of `MainWindow`; import execution, print execution, session rebinding, and project-tree workspace commands are behind service/controller boundaries, while direct mutation of serializable project objects remains the next target;
- define one screen/print grid contract and golden-render fixtures;
- add report provenance: source fingerprints, channel bindings, UOM, formula versions,
  locale, template revision, and render settings;
- test project format v15 and layout format v14 migrations with representative legacy files.

Exit: bounded controllers with headless tests, stable visual fixtures, reproducible report passport.

## Phase 2 — semantic data and operational QC

- introduce canonical channel kinds based on quantity classes and an Energistics-compatible
  UOM dictionary while preserving original mnemonics;
- add an Import Review screen for mapping, units, index, NULL, gaps, duplicates, and warnings;
- store measurement time, arrival time, source, calibration, and QC flags;
- define typed drilling, gas, show, sample, casing, and formation-top events;
- add versioned lag/depth correction without rewriting the acquired source.

Exit: the same channel is found consistently across vendors; every correction is reversible and audited.

## Phase 3 — WITSML real-time path

1. Read-only WITSML 2.1 object inventory and mapping fixtures.
2. Recorded replay into an append-only growing dataset.
3. Checkpoints, reconnect, backpressure, gaps, duplicates, out-of-order and stale-data QC.
4. Secured ETP 1.2 client with credentials outside project files.
5. Structured MudLogReport views and acknowledged rules/alarms.

Exit: a recorded session can be replayed deterministically and produces the same audited result.

## Phase 4 — unified reports and multiwell work

- one interval report model for geology, cuttings, calcimetry, LBA, gas, drilling, and events;
- PDF plus tabular exports driven from the same selected interval and bindings;
- multiwell correlation canvas with tops, ties, independent depth ranges, and paginated PDF;
- template validation, versioning, import/export, and backward-compatible migrations.

Exit: screen, PDF, and exported tables agree for the same report definition.

## Phase 5 — controlled extensibility

- versioned read-only API first, then explicit transaction-based edit commands;
- Python execution console with permissions, timeout, log, and no automatic execution from a project;
- crossplots and statistical plots as independent reusable view components;
- domain modules such as geomechanics, 3D, or AI import only after separate validation plans.

## Not on the immediate release path

Cloud collaboration, arbitrary proprietary formats, 3D reservoir modelling, autonomous AI
interpretation, and safety-critical well-control decisions are not commitments for version 1.0.

See [PRODUCT_AUDIT_2026.md](PRODUCT_AUDIT_2026.md) for evidence and competitor comparison.
