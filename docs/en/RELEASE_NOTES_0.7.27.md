# Release notes 0.7.27 — annotation deletion and form isolation

## Deletion fixed

- the **Delete annotation** context command now compares the `QMessageBox` result by value instead of Python object identity;
- after confirmation the object is removed from the well model, disappears from the tablet and creates one Undo operation;
- the focused editor for an existing annotation now has a dedicated **Delete annotation** button;
- the full annotation manager refreshes the tablet immediately after add, update, duplicate, delete, Undo and Redo without requiring the dialog to close;
- selection is cleared after deletion and actions for the removed object are disabled.
- the context menu compares the selected `QAction` by value and routes deletion through the single model controller;

## Annotations no longer leak into other forms

- every annotation receives a stable view scope for the current dataset and tablet form;
- comments, callouts, curve values and images are displayed only in the form where they were created;
- applying another form hides unrelated annotations, while returning to the original form restores them;
- changing tracks inside the current form does not change its annotation scope;
- saving the current tablet as a user form moves linked annotations to the new form scope;
- the screen tablet, PDF path and direct Masterlog renderer use the same scope filtering.
- after a form switch, a queued signal carrying a stale identifier cannot edit or delete an object owned by the previous form; the controller rechecks `scope_id` before the operation;

## Project compatibility

Older annotations without a view scope are bound automatically to the saved tablet form when the project is first opened in 0.7.27. Text, style, geometry, depth, time, curve binding, image assets and print settings remain unchanged.

## Verification

Added checks cover:

- CRUD and Undo/Redo after deletion;
- stable annotation scope while a form is edited;
- absence of an annotation in another form;
- restoration when the original form is reopened;
- migration of a legacy object without `scope_id`;
- persistence of `annotation_scope_id` in the tablet layout;
- the delete button in the focused editor;
- preventing well-global annotations from loading before the saved form is restored.
