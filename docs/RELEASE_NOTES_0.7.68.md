# GEOLOG GASRATIO@Pixler 0.7.68 — free stretching of catalog symbols

## User-visible change

- Catalog symbols inserted on tablet graphs now fill their complete annotation frame.
- Left/right handles change width only; top/bottom handles change height only.
- Corner handles freely change both dimensions, so a technical mark can be lengthened, flattened,
  made taller, or returned to a compact shape.
- Holding **Shift** during any resize preserves the starting aspect ratio.
- Normal imported images and photographs still preserve their original aspect ratio inside the frame.

## Persistence and output

The final width and height use the existing annotation geometry fields. One completed drag remains one
Undo/Redo operation. **Ctrl+S** stores the resulting geometry, reopening restores it, and the same
stretched symbol is used on screen, in preview, PDF, and physical printing.

## Compatibility

- Project format remains `v20`.
- Form schema remains `v8`.
- Tablet layout remains `v18`.
- Existing projects require no migration.
- The root `README.md` remains concise and unchanged.
