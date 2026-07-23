# Release notes 0.7.29 — unified import-job boundary

## Changes

- moved `ImportJobController` out of the Qt package into `services/import_jobs.py`;
- introduced one `DatasetImportJobExecutor` for CSV/Excel, LAS batches, and Paradox registration;
- removed LAS strict/compatible/manual policy, diagnostics, manual skip, and descending-depth
  detection from `MainWindow`;
- registered the lossless LAS source document and import report through one project-session port;
- committed the Paradox dataset and its separate well through the same boundary after the
  cancellable background import succeeds;
- ensured cancelled, rejected, or failed files cannot leave a partially registered dataset;
- corrected the loaded-LAS counter to report successfully committed files only;
- made the LAS adapter lazy so routing and CSV/Excel jobs remain importable without loading `lasio`.

## Compatibility

The project format, tablet format, LAS/DB files, and user workflow are unchanged. Source files
remain read-only.

## Verification

The expanded regression suite for import jobs, adapters, and the project-session boundary
reports 105 passed and 3 platform skips; `compileall` and the wheel build completed without errors. The full Ruff/mypy/pytest gate must be repeated in an installed environment with
all project dependencies.
