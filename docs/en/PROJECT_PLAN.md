# Project plan

Current as of 23 July 2026. Version history belongs in release notes; this file contains
only active work.

## P0 — release stability

- [x] fix annotation routing and the full Qt test-process crash;
- [x] bring Ruff and mypy to zero errors; the full pytest result is 1,217 passed and
  10 skipped;
- complete the mandatory Windows, HiDPI, PDF, and physical-print matrix;
- do not label the build stable until the gate is green.

## P0 — architecture and data

- [x] first extract the annotation event router from `TabletView` without changing behavior,
  protected by headless tests;
- [x] move pan, zoom, home/end, and keyboard commands into a headless navigation coordinator;
- [x] extract track plan/order/reuse and preserve chart instances through Undo/Redo;
- [x] extract track creation, rollback, and disposal with related registry cleanup;
- [x] extract a shared screen/print grid renderer with partial division updates;
- [x] make the editing-mode controller the sole owner of F4 and annotation-tool state;
- [x] extract home/workspace/target-tab navigation from `MainWindow`;
- [x] extract stable source kinds and universal-import routing;
- [x] extract CSV/Excel plan execution and dataset registration;
- extract LAS/Paradox jobs, print jobs, session binding, and remaining commands;
- add a Semantic Channel Dictionary with property kind, quantity class, UOM, aliases,
  source, and original mnemonic;
- add one Import Review and a reproducible report passport.

## P1 — operations and real time

- typed drilling, gas, show, sample, casing, and formation-top events;
- gap, duplicate, out-of-order, stale, and calibration QC;
- versioned lag/depth correction without changing the acquisition source;
- WITSML 2.1 inventory, recorded replay, then a secured ETP 1.2 client.

## P1 — reporting

- one interval model for preview, PDF, and tabular export;
- shared bindings, UOM, coverage, and explicit zero/missing handling;
- A4/A3/custom/roll, 100%/fit, and page-continuation verification.

## P2 — expansion

- multiwell correlation with tops, ties, and PDF;
- crossplots and statistical plots;
- a constrained versioned API and logged, permission-based Python console.

See the [engineering plan](../PROJECT_PLAN.md) for acceptance criteria and the
[audit](PRODUCT_AUDIT_2026.md) for evidence.
