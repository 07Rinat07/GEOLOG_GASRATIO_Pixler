# Release notes 0.7.31 — project-model mutation boundary

## Changes

- serializable tablet-layout changes now cross `TabletLayoutMutationController` and
  `TabletController` instead of direct assignments in the Qt view;
- track resize/reorder, vertical-index, and visible-range gestures keep their existing behavior
  and Undo/Redo while committing behind a controller boundary;
- `MainWindow` no longer writes `session.dirty`, project collections, or the current layout directly;
- `DerivedDatasetController` checkpoints merge/external-LAS copy operations and rolls them back
  after a cancelled or failed export;
- rollback removes the temporary dataset and layout/source/import-report sidecars, then restores
  the previous well/dataset selection and dirty state;
- merged-dataset names are validated before registration;
- Masterlog header image assets are validated and installed through one atomic controller call;
- the session registry now rebinds 27 controllers;
- headless, regression, and source-integrity coverage protects the boundary.

## Compatibility

Project format 15, layout format 14, and user workflows are unchanged. Source LAS files remain
untouched; only commit/rollback ownership changed.

## Verification

714 available tests passed and 4 platform-specific scenarios were skipped; `compileall` and the
0.7.31 wheel build completed successfully. The full Qt/LAS pytest, Ruff, mypy, and
Windows/HiDPI/PDF/physical-print gate must be repeated in an installed environment.
