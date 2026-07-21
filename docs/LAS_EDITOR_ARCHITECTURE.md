# LAS Editor 0.7.6 — Architecture

## Boundary

The LAS Editor is an orchestration layer over existing domain services. The UI hub
`ui/las_editor_dialog.py` does not parse or mutate files directly. It dispatches to:

- `services/new_las.py` — empty LAS dataset creation;
- `ui/las_table_editor.py` and range-edit controllers — in-memory table editing;
- `services/depth_axis.py` — ascending copies and depth resampling;
- `services/external_las_insert.py` — source analysis, unit-aware depth mapping and curve build;
- `services/dataset_merge.py` — depth-union splicing and overlap policies;
- `data/las_adapter.py` — validated LAS import/export.

## Copy-on-transform invariant

Operations that change depth geometry or combine sources return a new `Dataset` with a
new identity and `source_path=None`. `services/dataset_copy.py` deep-copies indexes,
curves and arrays and rewrites ownership metadata. Export therefore cannot overwrite an
input LAS by source-path identity.

External insertion uses `ExternalLasInsertController.create_copy()`. The old in-place
`apply()/undo()/redo()` API remains for backward compatibility and internal tests, but the
user-facing 0.7.6 workflow always creates a copy and requires a new output path.

## Non-standard input normalization

`sanitize_las_mnemonic()` keeps original source metadata and generates a portable output
mnemonic. It handles duplicate names exposed by lasio (`GK:1`, `GK:2`), Cyrillic and
separator-heavy labels. Descending sources are reversed in memory; their files are never
rewritten. Merge uses an in-memory ascending view with the original dataset identity.

## Failure handling

Insertion and merge create a derived dataset first and export it atomically. If export is
cancelled or fails, the UI removes the derived dataset and restores the previously selected
receiver. Input datasets and disk files are unchanged.
