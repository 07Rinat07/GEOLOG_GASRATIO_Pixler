# GEOLOG GASRATIO@Pixler 0.7.61

## Insert catalog symbols on graphs

Form edit mode **F4** now has a dedicated **Insert symbol** command. The dialog presents the
built-in symbol catalog with thumbnails, localized English names, categories, and search. The user
selects:

- a tightly cropped transparent variant or the original image with its background;
- the target graph track;
- a curve parameter anchor or a depth-only anchor;
- the exact depth and initial size.

The inserted symbol is selected automatically. It can be positioned precisely with the left mouse
button and resized through eight corner and side handles. The same workflow is available from the
graph context menu.

The selected symbol is copied into project-owned image storage and retains its catalog identifier
and background mode. No external BMP/PNG path is required. The object participates in Undo/Redo
and uses the same model for screen, PDF, and printer output.

## Compatibility and verification

Project format v20, form schema v6, and tablet layout v16 are unchanged. The available environment
completed **103 focused tests**, and `python -m compileall -q src tests` succeeded. The complete
Qt/UI suite could not run because PySide6, pyqtgraph, and lasio are unavailable in the container;
it remains mandatory in the installed Windows project environment.
