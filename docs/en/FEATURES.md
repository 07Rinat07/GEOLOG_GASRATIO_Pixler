# Features and instructions


## WITS0 normalized batches and append-only AcquisitionSession — 0.7.76

After a current Import Review, **File → Capture WITS Level 0...** starts an acquisition session for the current well. `Wits0FrameNormalizer` converts frames into deterministic immutable batches, while `Wits0AcquisitionRuntime` writes them only through the bounded `AcquisitionController`, with atomic enqueue, backpressure, checkpoints, and controlled close. Status shows pending/applied/skipped/checkpoints/backpressure, and the growing Dataset appears in the project immediately. See [WITS0_ACQUISITION.md](WITS0_ACQUISITION.md) and [WITS0_CAPTURE.md](WITS0_CAPTURE.md).

## WITS0 Import Review and immutable schema — 0.7.75

**File → Capture WITS Level 0...** now builds an immutable discovery snapshot of every data `record/item`. **Import Review…** shows types, UOM, samples, and QC; proposes Semantic Channel Dictionary mappings; supports time/depth index selection, hiding, and overrides; and atomically creates an immutable `AcquisitionDatasetSchema`. Mapping is stored in a separate versioned custom profile; numerical UOM conversion and `AcquisitionSession` remain the next increment. See [WITS0_CAPTURE.md](WITS0_CAPTURE.md).

## WITS Level 0 raw capture and parser — 0.7.74

**File → Capture WITS Level 0...** supports TCP server/client operation, append-only raw segments, a UTC chunk index, incremental `&& ... !!` framing, and automatic client reconnect. Socket work stays outside the Qt thread. Values are not yet committed to a Dataset. See [WITS0_CAPTURE.md](WITS0_CAPTURE.md).

## Workspace-bounded command rows and ultra-thin symbols — 0.7.72

Both top command rows live in an application-owned central host instead of the native `QMainWindow` toolbar area. They cannot raise the native window minimum width after F4, action-state, or DPI changes. Catalog-symbol width and height persist independently down to `0.01` logical pixel; this renders as the thinnest visible line, while a separate selection frame preserves mouse usability.

## On-screen toolbars and one-pixel symbols — 0.7.71

Both top toolbars have a hard cap based on the current window width and re-adapt after F4, action-state, DPI or monitor changes. Catalog symbols no longer receive the generic 40×24 px rendering minimum and can be independently narrowed to 1×1 logical pixel with Ctrl+S persistence.

## Reliable toolbar fitting and tiny symbols — 0.7.70

- application-owned responsive row instead of native `QToolBar` overflow;
- **Form editing** pinned inside the right edge;
- automatic migration of commands into **`⋯`** on narrow or high-DPI screens;
- identical adaptation for the main and F4 toolbars;
- independent symbol narrowing in width or height down to 2 logical pixels;
- preserved small dimensions in project save, preview, PDF and printing.


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
| WITS0 data | TCP server/client, raw capture, frames, reconnect, replay-ready files | [WITS0 capture](WITS0_CAPTURE.md), [Acquisition replay](ACQUISITION_REPLAY.md) |
| Data import | LAS, CSV, Excel, TXT, GeoScape/Paradox, SKF, preview and mapping review | [Import Review](IMPORT_REVIEW.md), [LAS Editor](LAS_EDITOR.md), [Paradox](PARADOX_IMPORT.md), [SKF](SKF_IMPORT.md) |
| Import diagnostics | NULL, duplicates, depth/time, units, gaps, error log | [Import Review](IMPORT_REVIEW.md), [Application diagnostics](APPLICATION_DIAGNOSTICS.md) |
| Datasets | multiple wells and datasets, merge, daily append, replay | [Workspace](UI_WORKSPACE.md), [Acquisition replay](ACQUISITION_REPLAY.md) |
| LAS table editor | inspect and edit curves, ranges, new LAS, export | [LAS Editor](LAS_EDITOR.md), [LAS Editor 2](LAS_EDITOR_2.md) |
| Tablet | curve selection, tracks, scales, ranges, grids, forms, scrolling and cursor | [Workspace](UI_WORKSPACE.md), [Tablet Engine](TABLET_ENGINE_2.md) |
| Graph editing | pencil, point correction, Undo/Redo, safe rebuild | [Interaction architecture](TABLET_INTERACTION_ARCHITECTURE.md) |
| Annotations | callouts, comments, images, saved curve values, symbols | [Annotations](ANNOTATIONS.md) |
| Catalog symbols | transparent/original background, anchoring, independent width/height stretch, Shift aspect lock, save and reopen | [Annotations](ANNOTATIONS.md) |
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
3. After insertion, use the left mouse button for precise placement. Side handles stretch one axis, corner handles resize both axes freely, and **Shift** preserves the aspect ratio.
4. Press **Ctrl+S**. There is no separate Save Symbol button: the object is saved with the project.
5. Close and reopen the project. Verify position, size, depth, track, parameter, and background mode.
6. Check preview/PDF when required. PDF export does not replace project saving.

## Data that is not translated automatically

LAS mnemonics, units, object identifiers, user-authored names and descriptions, formulas, and
imported file content remain unchanged. The application interface and built-in user documentation
are localized.

## Verifying compact columns

1. Open a factory, ready, or user depth form.
2. After the one-time form schema **v8** / tablet layout **v18** migration, verify that
   stratigraphy, lithology, cuttings, calcimetry, LBA, and depth are **50%** narrower.
3. Curves and text must not be reduced automatically; their safety minimum is **80 px**.
4. Drag a compact column boundary or set the width in the inspector. The minimum is **48 px**.
5. Press **Ctrl+S**, close, and reopen the project. The selected widths must be restored.
6. Edit a ready form only through a separate user copy.

### Create and save while reviewing names

- **Create form** and **Save user form** open the same large reference window.
- It shows **all ready**, factory, and user forms before confirmation.
- Search covers names, descriptions, columns, and parameters.
- The selected form displays axis, type, revision, structure, widths, and mnemonics.
- A duplicate name is blocked case-insensitively after whitespace normalization.
- In save mode, matching an editable user form intentionally creates the next revision; a ready or
  factory template cannot be replaced.


## Catalog, toolbars, and diagnostics — 0.7.66

- Browse, create, and save workflows show the same Ready, **18 factory**, and user forms.
- Top toolbars are responsive: secondary captions are hidden when width is limited while
  **Form editing** remains inside the window.
- **Help → Clear diagnostics data…** removes only service logs and reports after confirmation;
  projects, LAS files, forms, and exported ZIP bundles remain untouched.

## Compact parameter rulers — 0.7.67

- The duplicated generic **Scale** caption is removed from numeric curve headers.
- Each ruler is labelled with its parameter name and unit, for example **Weight on bit · t**.
- One block uses 44 px instead of 58 px while retaining minimum/unit/maximum, `A`, and `⚙`.
- The common renderer applies the layout to every factory, ready, and user form.
- Project, form, and tablet schemas are unchanged; existing forms do not need to be resaved.

## Free catalog-symbol stretching — 0.7.68

- Side handles independently change a catalog symbol's width or height.
- Corner handles freely change both dimensions, allowing a long, tall, or compact technical mark.
- Holding **Shift** preserves the starting aspect ratio.
- Normal imported images remain undistorted and continue to fit with their aspect ratio preserved.
- The resulting width and height participate in Undo/Redo, persist with the project, and render the
  same way in preview, PDF, and print.

## Guaranteed top-toolbar placement — 0.7.69

- The responsive toolbar uses real logical button, system-font, and current-DPI metrics.
- Captions become icons when space is limited; if that is still insufficient, lower-priority commands
  move into the **“⋯”** menu.
- The right-side **Form editing** toggle is never hidden or moved into overflow.
- Recalculation runs after window, style, font, DPI, work-area, and monitor changes.
- The **“⋯”** menu uses the original actions, so shortcuts and command permissions are unchanged.
