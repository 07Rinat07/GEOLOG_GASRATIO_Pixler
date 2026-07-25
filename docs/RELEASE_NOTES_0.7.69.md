# GEOLOG GASRATIO@Pixler 0.7.69 — top toolbar always stays inside the window

## External-monitor toolbar fix

- The right-side **Form editing** command no longer depends on an approximate width threshold.
- Toolbar width is calculated from the real localized Qt button sizes in logical pixels.
- When space is limited, secondary captions are removed first.
- If even the ultra-compact row does not fit, lower-priority commands move into the **“⋯”** menu
  while the editing command remains visible at the right edge.
- The calculation runs after window resize, system-font or style changes, DPI/work-area changes, and
  moving the window between a laptop and an external monitor.
- Immediate and delayed checks cover late Windows metric updates after a screen transition.

## Using the compact toolbar

When commands are moved, press **“⋯”**. The menu contains the same Home, LAS Editor, Form Library,
Constructor, Open/Import, Save, Pencil, and Cursor Line actions. Shortcuts and application menus are
unchanged.

## Preserved 0.7.68 behavior

Independent symbol width/height stretching, **Shift** aspect locking, Undo/Redo, **Ctrl+S**
persistence, reopen, preview, PDF, and printing remain unchanged.

## Compatibility

Project format remains `v20`, form schema remains `v8`, and tablet layout remains `v18`. Existing
projects and forms require no migration. The root `README.md` is unchanged.
