# Roadmap — GEOLOG Gas Ratio & Pixler

Updated: 24 July 2026. The roadmap is ordered by risk and dependency. A phase is complete
only when its automated and manual acceptance criteria pass.

## Phase 0 — release recovery

- restore annotation event routing and eliminate the Qt test-process crash;
- resolve all Ruff findings and establish a decreasing, then zero, mypy baseline;
- make the complete pytest suite deterministic on the supported Windows environment;
- run the tablet, annotation, PDF, HiDPI, and physical-printer smoke matrix;
- publish a stable build only after every mandatory gate is green.
- keep RU/KK/EN user-document sets, links, save/reopen workflows, and i18n keys under an automated documentation gate.

Exit: Ruff = 0, mypy = 0, pytest = 0 failures, no process abort, signed smoke checklist.

## Phase 1 — maintainable tablet and reporting core

- split annotation routing, navigation, track lifecycle, grid rendering, and editing out of
  `TabletView`;
- keep state-changing workflows behind application boundaries; import/print execution, session rebinding, workspace commands, tablet layout mutations, derived-dataset rollback, project image assets, and interactive Import Review use controllers/services; Semantic Channel Dictionary and atomic review/commit are complete;
- [complete] define one screen/print grid contract and deterministic golden-render fixtures;
- [x] add deterministic report provenance: source fingerprints, interval-scoped channel data, complete semantic bindings/UOM, formula versions, locale, content-addressed template revision, and render settings;
- [x] resolve one immutable `ReportDefinition` and interval for Print Center preview/output, Masterlog, and selected CSV/XLSX export;
- test project format v20 (including v16 → v17 → v18 → v19 → v20), form schema v6, and layout format v16 migrations with representative legacy files.

Exit: bounded controllers, reproducible report passports, and deterministic structural/visual golden fixtures are complete; Windows raster/PDF/HiDPI validation remains.

## Phase 2 — semantic data and operational QC

- [complete] resolve canonical channel kinds through quantity classes and an explicit UOM
  dictionary while preserving source mnemonics and a version-stable binding snapshot;
- [complete] add an interactive Import Review screen for mapping, units, index, NULL, gaps,
  duplicates, warnings, manual overrides, and one atomic acceptance command;
- [complete] store measurement time, arrival time, source, calibration, and QC flags in project format v17;
- [complete] define typed drilling, gas, show, sample, casing, and formation-top events;
- [complete] add versioned lag/depth correction without rewriting the acquired source.

Exit: the same channel is found consistently across vendors; every correction is reversible and audited.

## Phase 3 — WITSML real-time path

1. [complete] Recorded replay into an append-only growing dataset.
2. [complete] Checkpoints, controlled close, backpressure, and deterministic event/QC replay.
3. [complete] Versioned lag/depth correction as immutable derived projections.
4. Read-only WITSML 2.1 object inventory and mapping fixtures.
5. Secured ETP 1.2 client with credentials outside project files.
6. Structured MudLogReport views and acknowledged rules/alarms.

Replay and lag/depth correction exits are complete in 0.7.42 and 0.7.44. The remaining phase exit requires WITSML fixtures, secured
transport, reconnect coverage, and structured operational views.

## Phase 4 — unified reports and multiwell work

- [complete] one `ReportDefinition` and selected interval contract for geology, cuttings, calcimetry, LBA, gas, drilling, and events;
- [complete] Print Center/Masterlog PDF plus selected CSV/XLSX are driven from the same resolved interval;
- [complete] add shared coverage and an explicit zero/missing/unavailable-channel model;
- [complete] unify A4/A3/custom/roll media, Fit/100%, continuation planning, and the physical printer capability gate;
- completed: recoverable output + passport transaction and output-file fingerprints;
- [complete] DOCX/HTML adapters through the same ReportDefinition/Coverage/transaction boundary;
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
