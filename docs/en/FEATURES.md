# Features and instructions

This file is the current map of user-facing GEOLOG GASRATIO@Pixler features. Each area explains
what the feature does, where the command is located, and which document contains the complete
workflow. Historical build notes remain in release notes and do not replace the user guide.

## General working rules

- Changes to data, forms, intervals, and annotations first exist in the open project session.
- Use **Ctrl+S** or **File → Save** to write those changes to disk.
- When a modified project is closed, the application should offer to save it. Closing without
  saving discards everything changed after the last successful save.
- **Undo/Redo** reverses or reapplies supported operations only in the current session.
- LAS, CSV, Excel, PDF, DOCX, or HTML export creates a separate file and does not replace saving
  the project itself.
- After important changes, save the project, close it, and reopen it for a control check.

## User feature map

| Area | Main capabilities | Detailed instructions |
|---|---|---|
| Projects and language | startup, create/open project, RU/KK/EN, safe saving | [User guide](README.md) |
| Data import | LAS, CSV, Excel, TXT, GeoScape/Paradox, SKF, preview and mapping review | [Import Review](IMPORT_REVIEW.md), [LAS Editor](LAS_EDITOR.md), [Paradox](PARADOX_IMPORT.md), [SKF](SKF_IMPORT.md) |
| Import diagnostics | NULL, duplicates, depth/time, units, gaps, error log | [Import Review](IMPORT_REVIEW.md), [Application diagnostics](APPLICATION_DIAGNOSTICS.md) |
| Datasets | multiple wells and datasets, merge, daily append, replay | [Workspace](UI_WORKSPACE.md), [Acquisition replay](ACQUISITION_REPLAY.md) |
| LAS table editor | inspect and edit curves, ranges, new LAS, export | [LAS Editor](LAS_EDITOR.md), [LAS Editor 2](LAS_EDITOR_2.md) |
| Tablet | curve selection, tracks, scales, ranges, grids, forms, scrolling and cursor | [Workspace](UI_WORKSPACE.md), [Tablet Engine](TABLET_ENGINE_2.md) |
| Graph editing | pencil, point correction, Undo/Redo, safe rebuild | [Interaction architecture](TABLET_INTERACTION_ARCHITECTURE.md) |
| Annotations | callouts, comments, images, saved curve values, symbols | [Annotations](ANNOTATIONS.md) |
| Catalog symbols | transparent/original background, track, parameter, depth, move, resize, save and reopen | [Annotations](ANNOTATIONS.md) |
| Lithology and intervals | lithotypes, descriptions, stratigraphy, samples, calcimetry and LBA | [User guide](README.md), [Forms and stratigraphy](FORM_CAPTIONS_AND_STRATIGRAPHY.md) |
| Operational events | drilling, gas, shows, samples, casing, formation tops, QC | [Operational events](OPERATIONAL_EVENTS.md) |
| Channels and Sensors | semantic kinds, units, bindings, sensor catalog | [Semantic dictionary](SEMANTIC_CHANNEL_DICTIONARY.md) |
| Calculations | Gas Ratio, normalized gas, DEXP/NCT, custom formulas | [User guide](README.md) |
| Lag/depth | correction revisions, preview, derived dataset, rollback | [Lag/depth correction](LAG_DEPTH_CORRECTION.md) |
| Masterlog forms | library, independent headers, tracks, symbols | [Constructor](CONSTRUCTOR.md), [Form Engine](FORM_ENGINE.md) |
| Constructor | text, shapes, images, lithotypes, asset import, templates | [Constructor](CONSTRUCTOR.md) |
| Reports | ReportDefinition, passport, coverage, intervals, reproducibility | [Report definition](REPORT_DEFINITION.md), [Passport](REPORT_PASSPORT.md), [Coverage](COVERAGE_MODEL.md) |
| Printing and export | preview, A4/A3/roll, Fit/100%, PDF, physical printer | [Print Center](UNIVERSAL_PRINT_CENTER.md), [Report export](REPORT_EXPORT.md) |
| DOCX and HTML | document adapters through the shared report contract | [DOCX/HTML](DOCX_HTML_EXPORT.md) |
| Diagnostics | logs, system report, support ZIP without project/LAS copies | [Application diagnostics](APPLICATION_DIAGNOSTICS.md) |

## Verifying an inserted symbol

1. Open the tablet, press **F4**, and choose **Insert symbol**.
2. Select the background variant, track, parameter or depth-only anchor, depth, and size.
3. After insertion, use the left mouse button for precise placement and the handles for resizing.
4. Press **Ctrl+S**. There is no separate Save Symbol button: the object is saved with the project.
5. Close and reopen the project. Verify position, size, depth, track, parameter, and background mode.
6. Check preview/PDF when required. PDF export does not replace project saving.

## Data that is not translated automatically

LAS mnemonics, units, object identifiers, user-authored names and descriptions, formulas, and
imported file content remain unchanged. The application interface and built-in user documentation
are localized.
