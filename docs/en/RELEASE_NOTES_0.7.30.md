# Release notes 0.7.30 — print jobs, session binding, and workspace commands

## Changes

- introduced `PrintJobExecutor` in `services/print_jobs.py`; it configures `QPrinter` and
  executes physical printing, PDF output, and paged raster/SVG export through one renderer;
- reduced `MainWindow` to source selection, Qt dialogs, overwrite confirmation, and result display;
- introduced `SessionBindingController`, which rebinds 26 session-aware controllers through one
  registry after a project is opened;
- clear Undo/Redo history, transient selections, and unfinished state when the project session
  changes, preventing controllers from continuing against the previous session;
- fixed rebinding of TIME↔DEPTH mapping/conversion and LAS range-editor histories;
- introduced `WorkspaceCommandController` to validate project-tree payloads, select well/dataset
  context, and route curve, track, lithology, stratigraphy, and interpretation commands;
- made stale or malformed tree items atomic: they no longer partially change the active dataset;
- removed direct `current_well_id` and `current_dataset_id` assignments from the `MainWindow`
  tree handler.

## Compatibility

The project format, tablet format, print settings, and user workflow are unchanged. Preview, PDF,
file export, and the system printer continue to use the existing document model and renderer.

## Verification

The expanded headless/regression/source-integrity suite reports 73 passed; `compileall` and the
0.7.30 wheel build completed without errors. The full Ruff/mypy/Qt gate and physical-printer
smoke test must be repeated in an installed Windows environment with all dependencies.
