# Hotfix report 0.7.27

## User-reported defects

1. The annotation context menu displayed **Delete annotation**, but confirmation did not remove the object on Windows.
2. The focused annotation editor had no delete action.
3. Changes made in the full annotation manager were not reflected on the tablet until the dialog closed.
4. Annotations created in one tablet form appeared in other forms for the same well.

## Root causes

- `QMessageBox.StandardButton` was compared with Python identity operators (`is` / `is not`). PySide may return an equivalent enum wrapper that is not the same Python object, so the confirmation branch returned without deleting.
- Annotation records were stored only at well level and had no view/form scope.
- The tablet received the complete well canvas-object list before the saved tablet layout was restored.
- The focused editor implemented Save/Cancel only.

## Implementation

- changed annotation confirmation to value comparison (`!=`);
- compare the selected context-menu `QAction` by value;
- reject a stale queued annotation identifier when its `scope_id` is not the active form scope;
- added a destructive delete button to the focused editor;
- added `annotations_changed` and live layer refresh after all annotation CRUD/history actions;
- introduced annotation schema version 2 with `scope_id`;
- introduced persistent `TabletLayout.annotation_scope_id` and layout format version 13;
- assigned stable dataset/form scopes in `FormApplyEngine` and the default tablet builder;
- filtered screen and Masterlog print rendering by the active scope;
- migrated legacy unscoped objects to the saved/current form once;
- rebound annotations when the current tablet is saved as a user form;
- prevented well-global objects from being passed to the tablet before layout restoration.

## Compatibility

The project JSON structure remains backward compatible. Layout versions 1–12 migrate to version 13. Annotation objects without `scope_id` are preserved and assigned to the current saved form. No source LAS/DB/PX/TV/FAM files are modified.

## Automated verification

- annotation CRUD, delete and Undo/Redo;
- cross-form visibility isolation, including forms with identical track structures;
- deletion from the persistent model plus Undo restoration in the same scope;
- rejection of stale cross-form edit/delete identifiers;
- return to original form;
- legacy scope migration;
- scope rebinding when saving a user form;
- tablet-layout scope serialization and v12 migration;
- source guards for the context confirmation, focused-editor delete button and scoped project loading;
- project-codec and tablet-layout regression tests.

## Remaining release gate

A real Windows test with PySide6/pyqtgraph is still required for pointer interaction, visual rendering, PDF and physical print comparison. This package must remain marked TEST until that validation is completed.
