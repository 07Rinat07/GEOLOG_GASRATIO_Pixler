# Release notes 0.7.17

## Purpose

This hotfix corrects real professional-annotation interaction failures found during manual validation of 0.7.16. The project format and persisted annotation schema are unchanged.

## Fixed

- the F4 Callout, Comment and Image actions open the editor again;
- creation from the toolbar or graph context menu uses a focused Save/Cancel dialog;
- text, style, offset, width and height can be edited before saving;
- existing boxes drag, resize from the lower-right handle and open on double-click;
- right-clicking an object opens its object menu instead of the track menu;
- new callouts have a clearly visible leader between anchor and text box;
- the GeoScape 0.2 m standard is displayed separately from the DB file’s actual step. The supplied BLData retains LAS `STEP=0.4` until explicitly resampled.

## Compatibility

0.7.15/0.7.16 projects open without migration. Source LAS/DB files are never modified.

