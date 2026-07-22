# Project plan

Current as of 23 July 2026. Version history belongs in release notes; this file contains
only active work.

## P0 — release stability

- fix annotation routing and the full Qt test-process crash;
- bring Ruff, mypy, and all 1169 tests to zero errors;
- complete the mandatory Windows, HiDPI, PDF, and physical-print matrix;
- do not label the build stable until the gate is green.

## P0 — architecture and data

- split `TabletView` into annotation, navigation, track, grid, and editing controllers;
- split `MainWindow` into workspace, import, print, and session-binding commands;
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
