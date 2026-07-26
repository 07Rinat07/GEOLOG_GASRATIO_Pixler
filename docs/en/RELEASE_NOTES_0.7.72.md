# GEOLOG GASRATIO@Pixler 0.7.72 — command rows outside native QToolBar and practically unrestricted symbol narrowing

## Interface adaptation

- The main command row and the **Form editing (F4)** row are no longer `QToolBar` instances and are not placed in the native `QMainWindow` toolbar area.
- Both rows are plain `QFrame` containers above the workspace and are physically bounded by the central-area width; Qt has no native extension button in this path.
- Action-state changes, F4 toggling, laptop/external-monitor transfer, and DPI changes can no longer increase the native window minimum width.
- A final safety boundary caps the main-window minimum size to the active monitor work area.
- The right-side **Form editing** command stays inside the window; lower-priority commands move to icons and the **`⋯`** menu.

## Graph symbols

- The practical stored-geometry floor is reduced to `0.01` logical pixel; rendering still produces the thinnest visible one-device-pixel line.
- Width and height remain independent: side handles change one axis, corner handles change both, and **Shift** preserves the aspect ratio.
- A very thin symbol receives a separate usable selection frame of at least `18×18 px`; this frame does not change or persist as the symbol geometry.
- The thin symbol can be selected again, stretched, and moved after **Ctrl+S** and project reopen.
- Normal images, comments, and callouts retain the safe `40×24 px` minimum.

## Related fixes

- CSV/XLSX driven by one `ResolvedReportDefinition` now exports an active numeric TIME index from
  the exact resolved rows, with TIME in the first column and neutral interval-boundary metadata.
- The interval-statistics overlay retains enough free space for meaningful manual movement after
  resize.
- Duplicate UI import modules were removed; all five sources use the shared
  `DatasetImportJobExecutor` and Import Review.

Project format remains `v20`, form schema `v8`, and tablet layout `v18`.
