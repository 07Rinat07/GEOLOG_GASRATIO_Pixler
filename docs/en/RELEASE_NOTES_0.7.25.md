# Release notes 0.7.25 — in-batch DB configuration and safe tablet rendering

Status: **test build** until mandatory visual verification on Windows.

## Batch DB → LAS

- an ambiguous index is no longer reported as a generic error;
- the row receives a **Configuration required** status;
- **Configure selected DB…** opens the normal GeoScape/Paradox dialog;
- the user selects depth, time, channels and units without opening a document;
- the selected plan is retained for the current session and reused for depth/time export;
- after configuration, the dialog offers to retry only the selected file;
- real failures, existing-output skips and configuration requests are visually distinct.

## Tablet and annotations

- removed the full-size translucent `QWidget` that could cover PyQtGraph with a black rectangle on Windows;
- `TabletAnnotationOverlay` is now a hidden geometry/signal manager and paints nothing itself;
- every visible annotation is rendered as a small independent `QLabel` sprite containing an alpha `QPixmap`;
- each sprite is limited to the actual object bounds and the graph body below headers;
- empty tablet regions have no annotation child window above them;
- pointer routing, track editing, Undo/Redo and print rendering remain intact.

## Validation

Compilation, unit/source-contract tests, localization parity and real Paradox samples were checked in the container. A real `PySide6 + pyqtgraph` Windows render is unavailable here, so this package is not declared stable.
