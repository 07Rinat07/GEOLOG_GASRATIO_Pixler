# Release notes 0.7.21

- removed translucent-overlay flicker while dragging/resizing callouts and comments;
- mouse movement repaints only the changed object rectangle instead of the complete tablet;
- the native QWidget mask is cached and is not reapplied for every mouse event;
- geometry is committed once on release and only after an actual move/resize;
- a selection click no longer creates an Undo command or marks the project dirty;
- canvas-object and image-asset synchronization no longer rebuilds tracks, curves or headers;
- annotation operations no longer refresh the project tree because annotations are managed by the dedicated layer manager.

The project format is unchanged and existing annotations remain compatible.
