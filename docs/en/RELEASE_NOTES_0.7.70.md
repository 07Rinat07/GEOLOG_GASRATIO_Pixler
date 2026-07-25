# GEOLOG GASRATIO@Pixler 0.7.70 — fixed responsive toolbar and unrestricted symbol narrowing

## Top toolbar

- The main toolbar now lives inside one constrained responsive container. The native `QToolBar` extension button can no longer appear after a monitor or DPI change and push the right-side command outside the window.
- **Form editing** is pinned to the right inside the available window width.
- When space is insufficient, labels switch to icons and lower-priority commands move into the application-owned **`⋯`** menu.
- The same row architecture is used by the **Form editing (F4)** toolbar.
- The layout is recalculated after window, system-font, style, DPI, work-area and monitor changes.

## Symbol size

- A symbol inserted from the built-in catalog can now be narrowed independently in width or height down to 2 logical pixels instead of the previous 48×28 px limit.
- Side handles change one axis; corner handles change both axes.
- Hold `Shift` to preserve the starting aspect ratio.
- Normal images, comments and callouts retain safe minimum dimensions.
- Small dimensions are stored in the project, restored after reopening and used by preview, PDF and printing.

Project format remains `v20`, form schema `v8`, and tablet layout `v18`.
