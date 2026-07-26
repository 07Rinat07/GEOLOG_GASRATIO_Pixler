# Project plan

## New track: GeoScape II GS2 import

- [x] safely identify, validate, and temporarily extract the `.gs2` ZIP container;
- [x] validate `GS2.mdb`, `GS2#*.db`, unsafe paths, duplicates, and extraction limits;
- [x] expose GS2 in universal import, the File menu, and drag-and-drop;
- [ ] read channel relationships from `GS2.mdb` through ACE/ODBC with driver diagnostics;
- [x] confirm Paradox 7.x format for every `GS2#*.db` table in the СГ-8 sample;
- [x] import a selected table with TIME/DEPTH, actual step, provenance, and QC;
- [x] feed the selected table into `Dataset` and Import Review;
- [ ] automatically merge multipart TIME tables;
- [ ] resolve channel names and units from `GS2.mdb` for Gas Ratio/Pixler and export;
- [x] preserve the source grid and create 0.2 m data only through explicit resampling;
- [ ] compare the result with reference LAS/Excel exports from GeoScape.

The current stage adds a selected table to the project. Full support requires automatic table
merging and reproducible channel mapping from `GS2.mdb`.



## Completed in 0.7.71

Fixed rightward interface expansion after F4/clicks on an external monitor, hard-capped both toolbars to the window width, and removed the hidden 40×24 px layout clamp for catalog symbols. Geometry persistence and RU/KK/EN documentation were verified.

Current as of 25 July 2026. Version **0.7.71** uses project format **v20**, form schema **v8**, tablet layout **v18**.

## Completed in 0.7.70

- removed the recurring native overflow arrow after interaction and monitor changes;
- added application-owned `⋯` overflow for both top toolbars;
- removed the 48×28 px catalog-symbol narrowing limit; the minimum visible size is 2×2 logical pixels;
- added regression coverage for toolbar composition and tiny-symbol geometry.


Current as of 25 July 2026. Version **0.7.70** uses project format **v20**,
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