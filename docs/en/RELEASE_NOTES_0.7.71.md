# GEOLOG GASRATIO@Pixler 0.7.71 — hard toolbar bounds and true symbol narrowing

## Interface toolbars

- The main toolbar and the **Form editing (F4)** toolbar can no longer enlarge the window minimum width.
- Both rows receive a hard cap based on the actual logical window width after DPI scaling.
- Layout is recalculated when the F4 toolbar is shown or hidden, when toolbar action state changes, and again after delayed Windows metric updates.
- The right-side **Form editing** command remains inside the window; lower-priority commands switch to icons and the application-owned **`⋯`** menu.
- Fixed the external-monitor scenario where repeated clicks caused the interface to be laid out wider than the screen.

## Graph symbols

- Removed the hidden generic `40×24 px` clamp from screen and print annotation layout.
- A catalog symbol can now truly be narrowed independently down to `1×1` logical pixel.
- Left/right handles change width, top/bottom handles change height, corner handles change both dimensions, and `Shift` preserves the aspect ratio.
- Normal images, comments and callouts keep the safe `40×24 px` minimum.
- Tiny geometry persists in the project and is used consistently on screen, in preview, PDF and printing.

Project format remains `v20`, form schema `v8`, and tablet layout `v18`.
