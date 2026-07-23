# 0.7.44 — versioned lag/depth correction

Test build. Project format v19; lag correction schema v1.

- immutable correction profiles with contiguous revisions;
- constant-time, annular-volume/flow, pump-stroke, and manual control-point methods;
- one derived dataset per revision with source and corrected depth axes;
- no rewriting of the acquisition dataset or append-only journal;
- source-prefix/output fingerprints and load-time replay verification;
- formula, parameter, index, curve, author, timestamp, and acquisition provenance;
- optimistic add/activate guards and reversible active-revision selection;
- localized Qt workflow with preview and explicit source/corrected axis selection;
- safe `v18 → v19` migration.

Checks: 72 focused passed; available headless regression 987 passed, 4 skipped, 3 deselected.
The full Qt/LAS/Ruff/mypy and Windows smoke gates remain pending in this container.
