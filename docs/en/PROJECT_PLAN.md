# Project plan

Current as of 23 July 2026. Version history belongs in release notes; this file contains
only active work. UI hotfix 0.7.43 does not change the roadmap order: the next domain slice is
versioned lag/depth correction.

## P0 — release stability

- [x] fix annotation routing and the full Qt test-process crash;
- [x] bring Ruff and mypy to zero errors; baseline 0.7.28 reports 1,217 passed and
  10 skipped;
- complete the mandatory Windows, HiDPI, PDF, and physical-print matrix;
- repeat the full Ruff/mypy/pytest gate for the current version;
- do not label the build stable until the gate is green.

## P0 — architecture and data

- [x] extract the annotation event router from `TabletView` without changing behavior;
- [x] move pan, zoom, home/end, and keyboard commands into a headless coordinator;
- [x] extract track plan/order/reuse, creation, rollback, and disposal;
- [x] extract a shared screen/print grid renderer;
- [x] make the editing-mode controller the sole owner of F4 and annotation-tool state;
- [x] extract home/workspace/target-tab navigation from `MainWindow`;
- [x] extract universal-import routing and CSV/Excel/LAS/Paradox jobs;
- [x] extract print jobs, session binding, and project-tree workspace commands;
- [x] prevent UI classes from directly mutating the serializable project model;
- [x] add a Semantic Channel Dictionary with property kind, quantity class, UOM, aliases,
  source, and original mnemonic; bindings introduced in v16 remain persisted in current v18;
- [x] add an interactive Import Review with manual overrides, QC preview, and atomic commit;
- [x] add a reproducible report passport with fingerprints, bindings/UOM, formula versions, form revision, language, and render settings;
- [x] add deterministic golden fixtures for screen/print grids, legends, lithotypes, and annotations;
- [x] unify `ReportDefinition` and interval selection for preview, PDF, and tabular export;
- [x] add coverage and an explicit zero/missing/unavailable-channel distinction.

## P1 — operations and real time

- [x] typed drilling, gas, show, sample, casing, and formation-top events in project format v17;
- [x] gap, duplicate, out-of-order, stale, and calibration QC;
- [x] append-only growing dataset, checkpoint, and deterministic replay;
- [ ] versioned lag/depth correction without changing the acquisition source;
- [ ] offline WITSML 2.1 inventory and mapping fixtures, then a secured ETP 1.2 client after fixture replay.

## P1 — reporting

- [x] one interval model for preview, PDF, and tabular export;
- [x] shared bindings, UOM, coverage, and explicit zero/missing/unavailable handling;
- [x] A4/A3/custom/roll, Fit/100%, continuation, and physical printer gate;
- [x] one recoverable output + passport filesystem transaction and output fingerprint.
- [x] DOCX and HTML adapters through the shared ReportDefinition/Coverage contract and output transaction.

## P2 — expansion

- multiwell correlation with tops, ties, and PDF;
- crossplots and statistical plots;
- a constrained versioned API and logged, permission-based Python console.

See the [engineering plan](../PROJECT_PLAN.md) for acceptance criteria and the
[audit](PRODUCT_AUDIT_2026.md) for evidence.
