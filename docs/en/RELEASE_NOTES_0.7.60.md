# GEOLOG GASRATIO@Pixler 0.7.60

The interval-statistics panel was moved from a native floating `QDockWidget` to an in-tablet
overlay. It no longer consumes form width, cannot leave the tablet workspace, and preserves a
user-selected position when the main window is resized. Closing the panel or switching forms
clears interval selection, shading, dataset selection, and the report.

Pure geometry, source-contract, and Qt regression tests were added. The root README now contains
only the project overview, startup instructions, and documentation links; technical release
history remains under `docs`.

Project format v20, form schema v6, and tablet layout v16 are unchanged.
Container verification: 19 focused tests passed; the available headless regression completed with 1094 passed, 4 skipped, and 3 deselected. Qt scenarios require PySide6.
