# GEOLOG GASRATIO@Pixler project status

## Completed in 0.7.70

- the main and F4 toolbars use one constrained responsive row without native Qt overflow;
- the right-side editing control remains inside the window;
- catalog symbols can be narrowed independently to 2 logical pixels and retain their size after Ctrl+S/reopen.


Snapshot: 25 July 2026. Package version: **0.7.70**. Project format: **v20**,
form schema: **v8**, tablet layout: **v18**.

## Completed in 0.7.69

- the top toolbar selects expanded, compact, or ultra-compact mode from the actually measured
  localized button widths in Qt logical pixels;
- the fixed resolution threshold was removed: calculation includes the system font, style, and DPI;
- when even icon-only mode does not fit, lower-priority commands move into the **“⋯”** menu;
- the right-side **Form editing** toggle is not removable and remains inside the available toolbar width;
- recalculation runs after window, font, style, DPI, screen geometry/work-area, and monitor changes;
- immediate and delayed metric checks run after moving the window between a laptop and external monitor;
- user documentation, release notes, and regression tests are synchronized across RU/KK/EN.

## Retained from 0.7.68

- catalog symbols stretch independently in width and height;
- side handles resize one axis, corner handles resize both axes, and **Shift** preserves proportions;
- normal imported images remain undistorted;
- width and height participate in Undo/Redo, persist through **Ctrl+S**, restore after reopening, and
  render consistently on screen, in preview, PDF, and print.

## Retained from previous versions

Compact 44 px parameter headers without the duplicate **Scale** caption, compact geology columns,
one complete catalog of ready, **18 factory**, and user forms, the complete create/save form dialog,
and **Clear diagnostics data…** remain unchanged.

## Compatibility

Project format, form schema, and tablet layout are unchanged. Existing projects and forms require no
migration. The root `README.md` remains concise and contains no detailed fix history.
