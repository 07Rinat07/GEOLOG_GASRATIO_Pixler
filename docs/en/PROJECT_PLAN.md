# GEOLOG GASRATIO@Pixler project plan

Current as of 25 July 2026. Version **0.7.69** uses project format **v20**,
form schema **v8**, and tablet layout **v18**.

## Completed in 0.7.69

- [x] replace the fixed toolbar threshold with actual localized-button measurement;
- [x] support expanded, compact, and ultra-compact modes;
- [x] add the **“⋯”** overflow menu as the final clipping safeguard;
- [x] keep the right editing command outside the removable-action list;
- [x] recalculate after window, DPI, font, style, and screen work-area changes;
- [x] run immediate and delayed checks after monitor transfer;
- [x] update synchronized RU/KK/EN documentation and tests.

## Retained from 0.7.68

- [x] independent catalog-symbol width and height changes;
- [x] single-axis side handles and free two-axis corner handles;
- [x] **Shift** for proportional resizing;
- [x] preserved Undo/Redo, **Ctrl+S**, reopening, preview, PDF, and print behavior;
- [x] unchanged project v20, form v8, and tablet v18 schemas.

## Next stage

- [ ] visually verify the toolbar on Windows at 100%, 125%, and 150% scaling, including moving the
  window between a laptop and external monitor;
- [ ] verify horizontal/vertical stretching with transparent and original-background symbols;
- [ ] verify **Shift** with all eight handles and rotated objects;
- [ ] continue the approved project plan after user acceptance.

## Acceptance criterion

The right editing command is fully visible on the external monitor and laptop. When space is short,
captions disappear first and lower-priority commands remain available in **“⋯”**. A symbol can be
stretched on one or both axes, stored with **Ctrl+S**, and restored identically after reopening and in
preview, PDF, and print.
